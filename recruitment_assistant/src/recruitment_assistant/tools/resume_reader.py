"""Resume reader tool.

Used by the Parser and Coach agents to retrieve the candidate's resume
text. The resume is registered by main.py (or any runner) via
`register_resume_text` before `crew.kickoff()` runs. The agent then
obtains it by calling this tool - the text is NOT interpolated into
task descriptions, which forces the agent to invoke at least one tool
before it can produce any structured output about the resume.
"""

from __future__ import annotations

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel


_RESUME_STORE: dict[str, str] = {}


def register_resume_text(text: str) -> None:
    """Register the resume text that ResumeReaderTool will return."""
    _RESUME_STORE["resume"] = text


class ResumeReaderInput(BaseModel):
    """Input schema for ResumeReaderTool (no arguments)."""


class ResumeReaderTool(BaseTool):
    name: str = "resume_reader"
    description: str = (
        "Return the candidate's raw resume text exactly as provided at "
        "kickoff. Takes no arguments. Call this BEFORE any tool that "
        "needs the resume content (llm_structured_extract with "
        "target='resume', or llm_structured_coach's resume_text arg)."
    )
    args_schema: Type[BaseModel] = ResumeReaderInput

    def _run(self) -> str:
        text = _RESUME_STORE.get("resume", "")
        if not text:
            return ""
        return text
