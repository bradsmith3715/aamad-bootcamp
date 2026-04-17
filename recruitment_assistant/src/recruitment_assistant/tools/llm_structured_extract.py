"""LLM-backed structured extraction tool.

Used by the Parser agent per PRD §3 and SAD §2. Given a single resume or
a single job description, returns a schema-conforming JSON extraction
(ParsedResume or ParsedJob). The Parser agent typically invokes this tool
once per JD plus once for the resume, and aggregates the results into a
ParsedBundle.

Design:
- One call = one document. Keeps per-JD failures isolated.
- LLM is invoked with a schema-specific prompt. Response is parsed as
  JSON and validated against the target Pydantic model.
- Validation / LLM / parse failures collapse into a degraded result
  with a code and reason — the Parser agent decides whether to retry
  or record the JD as parse_status='degraded'.
- Span offsets are filled best-effort via source.find(text); -1 when
  the verbatim span cannot be located (per SAD §4 Span invariant).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ValidationError

from recruitment_assistant.schemas import ParsedJob, ParsedResume
from recruitment_assistant.tools._llm import llm_complete, parse_json_object


logger = logging.getLogger(__name__)

ExtractTarget = Literal["job", "resume"]


class LLMStructuredExtractInput(BaseModel):
    """Input schema for LLMStructuredExtractTool."""

    content: str = Field(
        ...,
        description="Free-form text to extract from (a resume or a single job description).",
    )
    target: ExtractTarget = Field(
        ...,
        description="Which schema to extract into: 'resume' or 'job'.",
    )
    job_id: Optional[str] = Field(
        default=None,
        description="Required when target='job'. Stable id of the source job (from JobList.id).",
    )


class LLMStructuredExtractTool(BaseTool):
    name: str = "llm_structured_extract"
    description: str = (
        "Extract structured records from free-form resume or job-description text. "
        "Call this tool once per document: once for the candidate's resume "
        "(target='resume'), and once per job (target='job', job_id=<the source Job id>). "
        "Returns a JSON string with 'status' ('ok' or 'degraded'), the extracted "
        "record under 'data', and a 'code'/'reason' pair when degraded."
    )
    args_schema: Type[BaseModel] = LLMStructuredExtractInput

    def _run(
        self,
        content: str,
        target: ExtractTarget,
        job_id: Optional[str] = None,
    ) -> str:
        if target == "job" and not job_id:
            return _degraded("missing-job-id", "target='job' requires a job_id.")
        if not content or not content.strip():
            return _degraded("empty-content", "content is empty.")

        try:
            raw = llm_complete(_build_prompt(target, content, job_id))
        except Exception as e:  # LLM/provider failures surface as a wide set of types.
            logger.warning("llm_structured_extract: LLM call failed: %s", e)
            return _degraded("llm-call-failed", str(e))

        data, parse_err = parse_json_object(raw)
        if data is None:
            return _degraded("invalid-json", parse_err or "LLM returned non-JSON.")

        try:
            if target == "resume":
                model = ParsedResume.model_validate(data)
                _locate_resume_spans(model, source=content)
                payload: Any = model.model_dump()
            else:
                data.setdefault("job_id", job_id)
                model_job = ParsedJob.model_validate(data)
                payload = model_job.model_dump()
        except ValidationError as e:
            logger.warning("llm_structured_extract: schema validation failed: %s", e)
            return _degraded("schema-invalid", str(e))

        return json.dumps(
            {"status": "ok", "target": target, "data": payload},
            ensure_ascii=False,
        )


# --- Prompting -----------------------------------------------------------

_RESUME_SCHEMA_SPEC = """\
Return a JSON object matching this schema:

{
  "skills": [string, ...],
  "experience_items": [
    {
      "title": string,
      "company": string,
      "start": string,
      "end": string | null,
      "bullets": [{"text": string}, ...]
    },
    ...
  ],
  "education": [
    {"degree": string, "institution": string, "start": string | null, "end": string | null},
    ...
  ],
  "years_experience_total": integer | null
}

Rules:
- Prefer null and empty lists over invention. Unknown values are null.
- Every bullet "text" must be a verbatim span from the resume; do not paraphrase.
- "skills" contains distinct technical or functional skills explicitly mentioned.
- "start" / "end" are ISO year-month strings like "2023-04"; "end" is null for current roles.
- "years_experience_total" is your best estimate from the experience items; null if unclear.
"""

_JOB_SCHEMA_SPEC = """\
Return a JSON object matching this schema:

{
  "skills": [string, ...],
  "must_have": [{"text": string, "tags": [string, ...]}, ...],
  "nice_to_have": [{"text": string, "tags": [string, ...]}, ...],
  "seniority": "intern" | "junior" | "mid" | "senior" | "staff" | "principal" | "unknown",
  "years_experience_min": integer | null
}

Rules:
- Every must_have / nice_to_have "text" must appear VERBATIM in the JD.
- Do not invent requirements. If a section is absent, return an empty list.
- "seniority" must be one of the enum values; use "unknown" when unclear.
- "years_experience_min": minimum stated (e.g., "5+ years" -> 5); null if unstated.
- "tags" are normalized skill tokens extracted from the requirement text (e.g., "Python", "Kubernetes").
"""


def _build_prompt(
    target: ExtractTarget, content: str, job_id: Optional[str]
) -> list[dict[str, str]]:
    if target == "resume":
        system = (
            "You are a precision extraction service. You convert resumes into strict "
            "JSON records. You prefer null over invention, and every text span you emit "
            "must be verbatim from the source.\n\n"
            + _RESUME_SCHEMA_SPEC
        )
        user = (
            f"Resume:\n\n{content}\n\n"
            "Return the JSON object only. No prose, no markdown fences."
        )
    else:
        system = (
            "You are a precision extraction service. You convert job descriptions into "
            "strict JSON records. You prefer empty lists over invention, and every text "
            "span you emit must be verbatim from the source JD.\n\n"
            + _JOB_SCHEMA_SPEC
        )
        user = (
            f"Job id: {job_id}\n\nJob description:\n\n{content}\n\n"
            "Return the JSON object only (do not include job_id in the output). "
            "No prose, no markdown fences."
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# --- Response post-processing --------------------------------------------


def _locate_resume_spans(model: ParsedResume, source: str) -> None:
    """Fill start_char / end_char on every Span in the ParsedResume.

    Uses source.find(text). Leaves the schema defaults (-1, -1) when the
    verbatim text cannot be located — the caller treats -1 as a signal
    that the span may need re-location at use time.
    """
    for item in model.experience_items:
        for span in item.bullets:
            if not span.text:
                continue
            idx = source.find(span.text)
            if idx >= 0:
                span.start_char = idx
                span.end_char = idx + len(span.text)


def _degraded(code: str, reason: str) -> str:
    return json.dumps(
        {"status": "degraded", "code": code, "reason": reason},
        ensure_ascii=False,
    )
