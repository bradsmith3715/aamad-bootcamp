"""LLM-backed multi-criterion ranking tool.

Used by the Ranking agent per PRD §3 and SAD §2. Given a ParsedResume and
a single ParsedJob, returns a RankedJob with a per-criterion fit breakdown,
an overall score in [0.0, 1.0], and a candidate-friendly reasoning summary.

The agent calls this tool once per ParsedJob with parse_status='ok', then
sorts the results by overall_score descending (deterministic tie-break by
job_id ascending per PRD §4 F-4) to produce the final RankedJobList.

Design invariants:
- Every must_have in the JD should appear as an explicit criterion
  (tasks.yaml ranking_task target: ≥90% coverage).
- required_in_jd is a verbatim span from the JD; evidence_in_resume.text
  is a verbatim span from the resume (skill name, bullet, title, etc.).
- status='missing' implies evidence_in_resume is null.
- A ParsedJob with parse_status='degraded' short-circuits to a typed
  degraded result so the agent records the skip rather than failing.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ValidationError

from recruitment_assistant.schemas import ParsedJob, ParsedResume, RankedJob
from recruitment_assistant.tools._llm import llm_complete, parse_json_object


logger = logging.getLogger(__name__)


class LLMStructuredRankInput(BaseModel):
    """Input schema for LLMStructuredRankTool."""

    parsed_resume_json: str = Field(
        ...,
        description="JSON-serialized ParsedResume (from llm_structured_extract with target='resume').",
    )
    parsed_job_json: str = Field(
        ...,
        description="JSON-serialized ParsedJob (from llm_structured_extract with target='job').",
    )


class LLMStructuredRankTool(BaseTool):
    name: str = "llm_structured_rank"
    description: str = (
        "Rank a single parsed job against the candidate's parsed resume. "
        "Call this tool once per ParsedJob whose parse_status is 'ok'. "
        "Inputs are JSON-serialized ParsedResume and ParsedJob objects. "
        "Returns a JSON string with 'status' ('ok' or 'degraded'), the "
        "RankedJob under 'data' (overall_score in [0.0, 1.0], per-criterion "
        "breakdown, reasoning_summary), and a 'code'/'reason' pair when degraded."
    )
    args_schema: Type[BaseModel] = LLMStructuredRankInput

    def _run(self, parsed_resume_json: str, parsed_job_json: str) -> str:
        try:
            resume_dict = json.loads(parsed_resume_json)
            job_dict = json.loads(parsed_job_json)
        except json.JSONDecodeError as e:
            return _degraded("invalid-input-json", f"input parse error: {e}")

        try:
            parsed_resume = ParsedResume.model_validate(resume_dict)
            parsed_job = ParsedJob.model_validate(job_dict)
        except ValidationError as e:
            return _degraded("input-schema-invalid", str(e))

        if parsed_job.parse_status == "degraded":
            return _degraded(
                "job-parse-degraded",
                f"ParsedJob {parsed_job.job_id} has parse_status='degraded'; ranking skipped.",
            )

        try:
            raw = llm_complete(_build_prompt(parsed_resume, parsed_job))
        except Exception as e:
            logger.warning("llm_structured_rank: LLM call failed: %s", e)
            return _degraded("llm-call-failed", str(e))

        data, parse_err = parse_json_object(raw)
        if data is None:
            return _degraded("invalid-json", parse_err or "LLM returned non-JSON.")

        # Inject job_id from the input to guarantee traceability even if the
        # LLM omits or mangles it.
        data["job_id"] = parsed_job.job_id

        try:
            ranked = RankedJob.model_validate(data)
        except ValidationError as e:
            logger.warning("llm_structured_rank: schema validation failed: %s", e)
            return _degraded("schema-invalid", str(e))

        return json.dumps(
            {"status": "ok", "data": ranked.model_dump()},
            ensure_ascii=False,
        )


# --- Prompting -----------------------------------------------------------

_SCHEMA_SPEC = """\
Return a JSON object matching this schema:

{
  "overall_score": float,                // 0.0 to 1.0
  "criteria": [
    {
      "name": string,                     // short label, e.g. "5+ yrs Python"
      "status": "matched" | "partial" | "missing",
      "required_in_jd": string,           // VERBATIM span from a JD requirement
      "evidence_in_resume": {"text": string} | null,
      "notes": string                     // one line, candidate-friendly
    },
    ...
  ],
  "reasoning_summary": string             // 1-2 sentences, candidate-friendly
}

Rules:
- Every must_have requirement from the JD MUST appear as an explicit criterion (target ≥90% coverage).
- Include nice_to_have requirements as criteria when meaningful.
- "matched"  = the resume clearly demonstrates the requirement.
- "partial"  = the resume partially demonstrates it (adjacent tech, fewer years, implied from context).
- "missing"  = no supporting evidence; evidence_in_resume MUST be null.
- "required_in_jd" must be a verbatim span from a JD requirement (must_have.text or nice_to_have.text).
- "evidence_in_resume.text" must be a verbatim span from the resume (a skill name, a bullet, a title).
- "overall_score" weighs matched > partial > missing; more missing must_haves = lower score.
- Keep notes terse; no internal jargon; write for the candidate.
"""


def _build_prompt(resume: ParsedResume, job: ParsedJob) -> list[dict[str, str]]:
    system = (
        "You are an explainability-first ranker. Given a parsed resume and a "
        "single parsed job description, you produce a per-criterion fit breakdown "
        "that cites evidence from the resume. You never collapse reasoning into a "
        "single opaque number; the breakdown is the product.\n\n"
        + _SCHEMA_SPEC
    )
    user = (
        "Parsed resume (structured):\n"
        + resume.model_dump_json(indent=2)
        + "\n\nParsed job (structured):\n"
        + job.model_dump_json(indent=2)
        + "\n\nReturn the JSON object only. No prose, no markdown fences. "
        "Do NOT include job_id in the output; it will be injected from the input."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _degraded(code: str, reason: str) -> str:
    return json.dumps(
        {"status": "degraded", "code": code, "reason": reason},
        ensure_ascii=False,
    )
