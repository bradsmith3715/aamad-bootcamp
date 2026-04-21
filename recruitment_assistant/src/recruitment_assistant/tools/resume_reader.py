"""Resume reader tool.

Used by the Parser and Coach agents to retrieve the candidate's resume
text. Reads `resume.txt` from the project root (four parents above this
module). Keeping the resume out of the task prompt forces the agents to
invoke a tool before producing any structured output about the resume.
"""

from __future__ import annotations

from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel


RESUME_PATH = Path(__file__).resolve().parents[3] / "resume.txt"


class ResumeReaderInput(BaseModel):
    """Input schema for ResumeReaderTool (no arguments)."""


class ResumeReaderTool(BaseTool):
    name: str = "resume_reader"
    description: str = (
        "Return the candidate's raw resume text from resume.txt at the "
        "project root. Takes no arguments. Call this BEFORE any tool "
        "that needs the resume content (llm_structured_extract with "
        "target='resume', or llm_structured_coach's resume_text arg)."
    )
    args_schema: Type[BaseModel] = ResumeReaderInput

    def _run(self) -> str:
        return RESUME_PATH.read_text(encoding="utf-8")
