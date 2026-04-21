#!/usr/bin/env python
import sys
import warnings

from recruitment_assistant.crew import RecruitmentAssistant
from recruitment_assistant.tools import register_resume_text

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your crew locally,
# so refrain from adding unnecessary logic into this file.
#
# Inputs below are interpolated into the task descriptions in
# src/recruitment_assistant/config/tasks.yaml:
#
#   {intent_prompt}   -> sourcing_task
#   {selected_job_id} -> coaching_task (PRD §3 T4)
#
# The resume text is NOT interpolated. It is registered with the
# ResumeReaderTool before kickoff; the Parser and Coach agents retrieve
# it by calling the tool, which forces them to invoke at least one tool
# before producing structured output about the resume.
#
# Replace the values below with whatever you want to test against. For the
# bootcamp single-pass demo, selected_job_id is a sentinel ("top_ranked")
# meaning "coach on whichever role ends up first after ranking." Once the
# ranker has real output you can re-run with a concrete job id.

SAMPLE_RESUME = """
Brad Smith — Backend Software Engineer

Experience:
- Platform Engineer, Acme Corp (2023–present)
  - Built Python microservices on FastAPI and Postgres serving 20k QPS.
  - Led migration from a Django monolith to a service-per-domain layout.
- Software Engineer, BetaCo (2021–2023)
  - Shipped Django-backed internal tools and REST APIs for operations.
  - Owned CI/CD pipeline on GitHub Actions and Docker.

Education:
- B.S. Computer Science, University of Nebraska–Lincoln, 2021.

Skills: Python, FastAPI, Django, Postgres, Docker, AWS, GitHub Actions.
""".strip()

SAMPLE_INTENT = "Remote Python platform or backend roles, mid-level, any US timezone."


def _default_inputs() -> dict:
    return {
        "intent_prompt": SAMPLE_INTENT,
        "selected_job_id": "top_ranked",
    }


def run():
    """Run the crew."""
    register_resume_text(SAMPLE_RESUME)
    try:
        RecruitmentAssistant().crew().kickoff(inputs=_default_inputs())
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """Train the crew for a given number of iterations."""
    register_resume_text(SAMPLE_RESUME)
    try:
        RecruitmentAssistant().crew().train(
            n_iterations=int(sys.argv[1]),
            filename=sys.argv[2],
            inputs=_default_inputs(),
        )
    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay():
    """Replay the crew execution from a specific task."""
    register_resume_text(SAMPLE_RESUME)
    try:
        RecruitmentAssistant().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test():
    """Test the crew execution and return the results."""
    register_resume_text(SAMPLE_RESUME)
    try:
        RecruitmentAssistant().crew().test(
            n_iterations=int(sys.argv[1]),
            eval_llm=sys.argv[2],
            inputs=_default_inputs(),
        )
    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


def run_with_trigger():
    """Run the crew with a trigger payload.

    The trigger payload is a JSON object passed as argv[1]. Any keys it
    provides override the default inputs, so an external trigger can
    supply a real resume / intent / selected_job_id without editing this
    file.
    """
    import json

    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload provided as argument")

    inputs = _default_inputs()
    inputs["crewai_trigger_payload"] = trigger_payload
    inputs.update({k: v for k, v in trigger_payload.items() if k in _default_inputs()})

    resume_text = trigger_payload.get("resume_text", SAMPLE_RESUME)
    register_resume_text(resume_text)

    try:
        return RecruitmentAssistant().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew with trigger: {e}")
