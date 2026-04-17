"""LLM-backed evidence-grounded resume coach tool.

Used by the Coach agent per PRD §3 T4 and SAD §2. Given a ParsedResume,
a RankedJob (the role the candidate selected), and the raw resume text,
returns a CoachPlan with two strictly separated outputs:

- edits: rewrites of EXISTING resume content. Every edit carries a
  non-null evidence_span pointing to verbatim resume content.
- gaps:  skills or experience the candidate lacks for the role. Never
  merged into edits, never used to introduce fabricated experience.

Two enforcement layers protect the "no hallucinated experience" invariant
(SAD §12 High risk, PRD §4 F-5):

1. Schema layer (Pydantic): CoachEdit.evidence_span is non-nullable.
   An edit without evidence fails validation and collapses the whole
   plan to a typed degraded result.
2. Runtime layer: every surviving edit is checked against the raw
   resume text; edits whose target_span or evidence_span is not a
   verbatim substring of the resume are dropped with a logged warning.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ValidationError

from recruitment_assistant.schemas import (
    CoachPlan,
    ParsedResume,
    RankedJob,
)
from recruitment_assistant.tools._llm import llm_complete, parse_json_object


logger = logging.getLogger(__name__)


class LLMStructuredCoachInput(BaseModel):
    """Input schema for LLMStructuredCoachTool."""

    parsed_resume_json: str = Field(
        ...,
        description="JSON-serialized ParsedResume (from llm_structured_extract with target='resume').",
    )
    ranked_job_json: str = Field(
        ...,
        description="JSON-serialized RankedJob (from llm_structured_rank) for the selected role.",
    )
    resume_text: str = Field(
        ...,
        description="Raw resume text, authoritative for verbatim span location and grounding checks.",
    )


class LLMStructuredCoachTool(BaseTool):
    name: str = "llm_structured_coach"
    description: str = (
        "Produce an evidence-grounded CoachPlan for a selected ranked role. "
        "Call this tool once the candidate selects a role from the ranked "
        "shortlist. Inputs: JSON-serialized ParsedResume, JSON-serialized "
        "RankedJob, and the raw resume text (for verbatim span validation). "
        "Returns a JSON string with 'status' ('ok' or 'degraded'), the "
        "CoachPlan under 'data' (edits[] and gaps[] strictly separated), "
        "any dropped-edit warnings under 'warnings', and a 'code'/'reason' "
        "pair when degraded."
    )
    args_schema: Type[BaseModel] = LLMStructuredCoachInput

    def _run(
        self,
        parsed_resume_json: str,
        ranked_job_json: str,
        resume_text: str,
    ) -> str:
        if not resume_text or not resume_text.strip():
            return _degraded("empty-resume", "resume_text is empty.")

        try:
            resume_dict = json.loads(parsed_resume_json)
            ranked_dict = json.loads(ranked_job_json)
        except json.JSONDecodeError as e:
            return _degraded("invalid-input-json", f"input parse error: {e}")

        try:
            parsed_resume = ParsedResume.model_validate(resume_dict)
            ranked_job = RankedJob.model_validate(ranked_dict)
        except ValidationError as e:
            return _degraded("input-schema-invalid", str(e))

        try:
            raw = llm_complete(
                _build_prompt(parsed_resume, ranked_job, resume_text)
            )
        except Exception as e:
            logger.warning("llm_structured_coach: LLM call failed: %s", e)
            return _degraded("llm-call-failed", str(e))

        data, parse_err = parse_json_object(raw)
        if data is None:
            return _degraded("invalid-json", parse_err or "LLM returned non-JSON.")

        # Inject job_id and synthesize stable edit ids before validation.
        # The LLM doesn't see the id field; the tool is the source of truth.
        data["job_id"] = ranked_job.job_id
        _assign_edit_ids(data, ranked_job.job_id)

        try:
            plan = CoachPlan.model_validate(data)
        except ValidationError as e:
            logger.warning("llm_structured_coach: schema validation failed: %s", e)
            return _degraded("schema-invalid", str(e))

        plan, warnings = _enforce_grounding(plan, resume_text)

        payload: dict[str, Any] = {"status": "ok", "data": plan.model_dump()}
        if warnings:
            payload["warnings"] = warnings
        return json.dumps(payload, ensure_ascii=False)


# --- Prompting -----------------------------------------------------------

_SCHEMA_SPEC = """\
Return a JSON object matching this schema:

{
  "edits": [
    {
      "target_section": "experience" | "skills" | "summary" | "projects" | "education",
      "target_span": {"text": string},         // existing resume content being edited; MUST be verbatim in the resume
      "suggested_text": string,                // your proposed rewrite
      "evidence_span": {"text": string},       // REQUIRED; verbatim span from the resume supporting the edit
      "rationale": string                      // one line, candidate-friendly
    },
    ...
  ],
  "gaps": [
    {
      "skill": string,                         // short name of the missing capability
      "why_it_matters": string,                // one sentence tied to the role
      "learn_path_hint": string | null         // brief suggestion or null
    },
    ...
  ]
}

Rules:
- You NEVER invent experience. If the candidate lacks a skill, it is a gap, not an edit.
- Every edit's target_span.text and evidence_span.text MUST appear VERBATIM in the raw resume text. Edits that fail this check are dropped.
- A skill listed in gaps MUST NOT appear as new experience inside any edit's suggested_text.
- Edits rewrite existing content; they do not add net-new experience. Rewrites may tighten, quantify (only with numbers already in the resume), or reframe.
- Keep edits focused on high-impact rewrites tied to this specific role: typically 3-6 edits.
- Keep gaps to what the role needs: typically 2-5 gaps.
- rationale and why_it_matters are one line each, candidate-friendly, no internal jargon.
"""


def _build_prompt(
    parsed_resume: ParsedResume,
    ranked_job: RankedJob,
    resume_text: str,
) -> list[dict[str, str]]:
    system = (
        "You are a cautious, candid resume coach. You never invent experience. "
        "Your credibility is the product. You would rather tell the candidate they "
        "have a skill gap than silently write an unsupported claim into their resume. "
        "You keep edits and gaps strictly separated: edits rewrite existing content; "
        "gaps label what the candidate needs to acquire.\n\n"
        + _SCHEMA_SPEC
    )
    user = (
        "Selected role (RankedJob, structured):\n"
        + ranked_job.model_dump_json(indent=2)
        + "\n\nParsed resume (structured):\n"
        + parsed_resume.model_dump_json(indent=2)
        + "\n\nResume (raw text; authoritative for verbatim spans):\n"
        + resume_text
        + "\n\nReturn the JSON object only. No prose, no markdown fences. "
        "Do NOT include job_id in the output; it will be injected from the input."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# --- Post-processing -----------------------------------------------------


def _assign_edit_ids(data: dict[str, Any], job_id: str) -> None:
    """Generate stable ids for each edit before Pydantic validation.

    Hash basis includes job_id so the same edit text against different
    roles produces different ids (edits are role-specific).
    """
    edits = data.get("edits")
    if not isinstance(edits, list):
        return
    seen: set[str] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            continue
        target_section = edit.get("target_section", "")
        evidence = (edit.get("evidence_span") or {}).get("text", "") or ""
        suggested = edit.get("suggested_text") or ""
        basis = f"{job_id}:{target_section}:{evidence}:{suggested}"
        edit_id = hashlib.sha256(basis.encode()).hexdigest()[:12]
        # Disambiguate the (unlikely) collision case deterministically.
        suffix = 0
        base_id = edit_id
        while edit_id in seen:
            suffix += 1
            edit_id = f"{base_id[:10]}{suffix:02d}"
        seen.add(edit_id)
        edit["id"] = edit_id


def _enforce_grounding(
    plan: CoachPlan, resume_text: str
) -> tuple[CoachPlan, list[str]]:
    """Drop edits whose spans are not verbatim in resume_text.

    Also fills start_char / end_char on surviving edits' spans so the UI
    and Coach task's downstream consumers can anchor edits precisely.
    """
    kept = []
    warnings: list[str] = []
    for edit in plan.edits:
        t_text = edit.target_span.text or ""
        e_text = edit.evidence_span.text or ""
        t_idx = resume_text.find(t_text) if t_text else -1
        e_idx = resume_text.find(e_text) if e_text else -1
        if t_idx < 0:
            warnings.append(
                f"dropped edit id={edit.id}: target_span not verbatim in resume"
            )
            continue
        if e_idx < 0:
            warnings.append(
                f"dropped edit id={edit.id}: evidence_span not verbatim in resume"
            )
            continue
        edit.target_span.start_char = t_idx
        edit.target_span.end_char = t_idx + len(t_text)
        edit.evidence_span.start_char = e_idx
        edit.evidence_span.end_char = e_idx + len(e_text)
        kept.append(edit)
    plan.edits = kept
    return plan, warnings


def _degraded(code: str, reason: str) -> str:
    return json.dumps(
        {"status": "degraded", "code": code, "reason": reason},
        ensure_ascii=False,
    )
