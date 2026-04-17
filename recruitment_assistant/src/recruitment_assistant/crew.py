from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent

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
)


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

    # --- Agents ---------------------------------------------------------

    @agent
    def sourcing_agent(self) -> Agent:
        # Tools per PRD §3 Sourcing Agent:
        #   - job_feed_fetcher  : live HN "Who is hiring?" feed (ToS-safe).
        #   - demo_corpus_reader: seeded 12-JD fallback corpus (SAD §6).
        return Agent(
            config=self.agents_config['sourcing_agent'],  # type: ignore[index]
            tools=[JobFeedFetcherTool(), DemoCorpusReaderTool()],
            verbose=True,
        )

    @agent
    def parser_agent(self) -> Agent:
        # Tool per PRD §3 Parser Agent:
        #   - llm_structured_extract: one-doc-at-a-time extraction invoked
        #     once per resume and once per JD to build the ParsedBundle.
        return Agent(
            config=self.agents_config['parser_agent'],  # type: ignore[index]
            tools=[LLMStructuredExtractTool()],
            verbose=True,
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
        )

    @agent
    def coach_agent(self) -> Agent:
        # Tool per PRD §3 Coach Agent:
        #   - llm_structured_coach: evidence-grounded CoachPlan for a
        #     selected role. Enforces the "no hallucinated experience"
        #     invariant at both the schema and runtime layers.
        return Agent(
            config=self.agents_config['coach_agent'],  # type: ignore[index]
            tools=[LLMStructuredCoachTool()],
            verbose=True,
        )

    # --- Tasks ----------------------------------------------------------
    # Declaration order is execution order under Process.sequential.

    @task
    def sourcing_task(self) -> Task:
        return Task(
            config=self.tasks_config['sourcing_task'],  # type: ignore[index]
            output_pydantic=JobList,
        )

    @task
    def parsing_task(self) -> Task:
        return Task(
            config=self.tasks_config['parsing_task'],  # type: ignore[index]
            output_pydantic=ParsedBundle,
        )

    @task
    def ranking_task(self) -> Task:
        return Task(
            config=self.tasks_config['ranking_task'],  # type: ignore[index]
            output_pydantic=RankedJobList,
        )

    @task
    def coaching_task(self) -> Task:
        return Task(
            config=self.tasks_config['coaching_task'],  # type: ignore[index]
            output_pydantic=CoachPlan,
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
        )
