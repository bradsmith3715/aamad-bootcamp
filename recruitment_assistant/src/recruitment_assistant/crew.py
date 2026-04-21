import os

from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.tasks.task_output import TaskOutput
from pydantic import BaseModel, ValidationError

from recruitment_assistant.schemas import (
    CoachPlan,
    JobList,
    ParsedBundle,
    RankedJobList,
)
from recruitment_assistant.tools import (
    DemoCorpusReaderTool,
    JobFeedFetcherTool,
    LLMStructuredCoachTool,
    LLMStructuredExtractTool,
    LLMStructuredRankTool,
    RemoteOkFetcherTool,
    ResumeReaderTool,
)


def _make_schema_guardrail(schema_cls: type[BaseModel]):
    """Return a guardrail that validates task.output.raw as JSON for schema_cls.

    Used instead of Task(output_pydantic=...), which would inject a
    response_format into the LLM call and short-circuit the ReAct tool
    loop (crew_agent_executor.py accepts a schema-matching first response
    as AgentFinish without ever invoking tools). This guardrail runs
    AFTER the agent has completed its tool loop, validates the JSON the
    agent returned, and re-emits it as the canonical string form.
    """
    def guardrail(task_output: TaskOutput):
        raw = (task_output.raw or "").strip()
        try:
            instance = schema_cls.model_validate_json(raw)
        except ValidationError as e:
            return (
                False,
                f"Final Answer must be valid JSON matching the "
                f"{schema_cls.__name__} schema. Validation error: {e}",
            )
        return (True, instance.model_dump_json())
    return guardrail


# Source of truth: project-context/1.define/product-requirements-document.md
#   §3 Task Orchestration (T1 Sourcing -> T2 Parse -> T3 Rank -> T4 Coach)
#   §4 Functional Requirements (F-2 .. F-5)
#
# Agent and task definitions live in:
#   src/recruitment_assistant/config/agents.yaml
#   src/recruitment_assistant/config/tasks.yaml
#
# Tool bindings and output_pydantic schemas are wired below, one per
# agent and task. Schemas live in recruitment_assistant.schemas.


@CrewBase
class RecruitmentAssistant():
    """Recruitment Assistant crew.

    A sequential CrewAI crew that runs the four PRD agents in order:
    sourcing -> parsing -> ranking -> coaching. On kickoff, expects the
    following inputs to be interpolated into the task descriptions:

        resume_text     - the candidate's resume (text/markdown)
        intent_prompt   - short career-intent prompt from the candidate
        selected_job_id - id of the role to coach on (per PRD §3 T4)

    PRD §3 separates the main pass (T1-T3) from on-demand coaching (T4).
    For the bootcamp demo this class wires all four into a single
    sequential crew; the production split into two crews is a Phase 2
    refinement.
    """

    agents: list[BaseAgent]
    tasks: list[Task]

    # Agent LLM with a generous max_tokens so the sourcing agent can echo
    # up to ~20 full HN job descriptions as JSON (each raw_description is
    # long; default Anthropic max_tokens truncates the Final Answer and
    # the JobList guardrail fails to parse the cut-off JSON).
    _llm = LLM(
        model=os.environ.get("MODEL", "anthropic/claude-sonnet-4-6"),
        max_tokens=32000,
    )

    # --- Agents ---------------------------------------------------------

    @agent
    def sourcing_agent(self) -> Agent:
        # Tools per PRD §3 Sourcing Agent:
        #   - job_feed_fetcher  : live HN "Who is hiring?" feed (ToS-safe).
        #   - remote_ok_fetcher : live RemoteOK public API feed.
        #   - demo_corpus_reader: seeded fallback corpus (SAD §6), only
        #                         used when BOTH live feeds return degraded.
        return Agent(
            config=self.agents_config['sourcing_agent'],  # type: ignore[index]
            tools=[
                JobFeedFetcherTool(),
                RemoteOkFetcherTool(),
                DemoCorpusReaderTool(),
            ],
            verbose=True,
            llm=self._llm,
            max_iter=6,
        )

    @agent
    def parser_agent(self) -> Agent:
        # Tools per PRD §3 Parser Agent:
        #   - resume_reader         : returns the resume text registered at
        #                             kickoff; keeps resume out of the prompt.
        #   - llm_structured_extract: one-doc-at-a-time extraction invoked
        #                             once per resume and once per JD.
        return Agent(
            config=self.agents_config['parser_agent'],  # type: ignore[index]
            tools=[ResumeReaderTool(), LLMStructuredExtractTool()],
            verbose=True,
            llm=self._llm,
            max_iter=40,
        )

    @agent
    def ranking_agent(self) -> Agent:
        # Tool per PRD §3 Ranking Agent:
        #   - llm_structured_rank: one-job-at-a-time multi-criterion ranking
        #     against the candidate's ParsedResume.
        return Agent(
            config=self.agents_config['ranking_agent'],  # type: ignore[index]
            tools=[LLMStructuredRankTool()],
            verbose=True,
            llm=self._llm,
            max_iter=40,
        )

    @agent
    def coach_agent(self) -> Agent:
        # Tools per PRD §3 Coach Agent:
        #   - resume_reader       : returns the resume text registered at
        #                           kickoff; passes to llm_structured_coach.
        #   - llm_structured_coach: evidence-grounded CoachPlan for a
        #                           selected role. Enforces the "no
        #                           hallucinated experience" invariant at
        #                           both the schema and runtime layers.
        return Agent(
            config=self.agents_config['coach_agent'],  # type: ignore[index]
            tools=[ResumeReaderTool(), LLMStructuredCoachTool()],
            verbose=True,
            llm=self._llm,
            max_iter=6,
        )

    # --- Tasks ----------------------------------------------------------
    # Declaration order is execution order under Process.sequential.

    @task
    def sourcing_task(self) -> Task:
        return Task(
            config=self.tasks_config['sourcing_task'],  # type: ignore[index]
            guardrail=_make_schema_guardrail(JobList),
        )

    @task
    def parsing_task(self) -> Task:
        return Task(
            config=self.tasks_config['parsing_task'],  # type: ignore[index]
            guardrail=_make_schema_guardrail(ParsedBundle),
        )

    @task
    def ranking_task(self) -> Task:
        return Task(
            config=self.tasks_config['ranking_task'],  # type: ignore[index]
            guardrail=_make_schema_guardrail(RankedJobList),
        )

    @task
    def coaching_task(self) -> Task:
        return Task(
            config=self.tasks_config['coaching_task'],  # type: ignore[index]
            guardrail=_make_schema_guardrail(CoachPlan),
        )

    # --- Crew -----------------------------------------------------------

    @crew
    def crew(self) -> Crew:
        """Sequential crew: sourcing -> parsing -> ranking -> coaching."""
        return Crew(
            agents=self.agents,   # populated by the @agent decorators above
            tasks=self.tasks,     # populated by the @task decorators above
            process=Process.sequential,
            verbose=True,
            llm=self._llm,
        )
