"""Pydantic schemas for agent I/O.

Source of truth: project-context/1.define/sad.md §4 Data Models.
Schemas are defined once here and reused across tools (extraction) and
tasks (output_pydantic binding) so invariants like "Coach edits require
an evidence_span" are enforced at the type layer rather than by hoping
the LLM behaves.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


Seniority = Literal["intern", "junior", "mid", "senior", "staff", "principal", "unknown"]
ParseStatus = Literal["ok", "degraded"]
CriterionStatus = Literal["matched", "partial", "missing"]
TargetSection = Literal["experience", "skills", "summary", "projects", "education"]


class Span(BaseModel):
    """A verbatim text span from the source document.

    start_char / end_char are -1 when the verbatim text could not be
    located in the source (best-effort offset location; see
    llm_structured_extract._locate_spans_in_place).
    """

    text: str
    start_char: int = -1
    end_char: int = -1


class Requirement(BaseModel):
    """A must-have or nice-to-have requirement from a job description."""

    text: str  # verbatim span from the JD
    tags: list[str] = Field(default_factory=list)


class Job(BaseModel):
    """A normalized job posting record, provider-agnostic.

    Matches the shape produced by both job_feed_fetcher (live HN) and
    demo_corpus_reader (seeded fallback) per PRD §3 T1 / SAD §4.
    """

    id: str
    title: str
    company: str
    location: Optional[str] = None
    url: str
    source: str  # e.g., "hn_whos_hiring", "demo_corpus"
    raw_description: str


class JobList(BaseModel):
    """Sourcing agent's aggregated output per PRD §3 T1."""

    jobs: list[Job] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    title: str
    company: str
    start: str  # ISO year-month, e.g. "2023-04"
    end: Optional[str] = None  # None for current / ongoing
    bullets: list[Span] = Field(default_factory=list)


class EducationItem(BaseModel):
    degree: str
    institution: str
    start: Optional[str] = None
    end: Optional[str] = None


class ParsedResume(BaseModel):
    skills: list[str] = Field(default_factory=list)
    experience_items: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    years_experience_total: Optional[int] = None


class ParsedJob(BaseModel):
    job_id: str
    skills: list[str] = Field(default_factory=list)
    must_have: list[Requirement] = Field(default_factory=list)
    nice_to_have: list[Requirement] = Field(default_factory=list)
    seniority: Seniority = "unknown"
    years_experience_min: Optional[int] = None
    parse_status: ParseStatus = "ok"


class ParsedBundle(BaseModel):
    """Parser agent's aggregated output per PRD §3 T2."""

    parsed_resume: ParsedResume
    parsed_jobs: list[ParsedJob] = Field(default_factory=list)


class Criterion(BaseModel):
    """A single fit criterion within a RankedJob."""

    name: str
    status: CriterionStatus
    required_in_jd: str  # verbatim span from the JD
    evidence_in_resume: Optional[Span] = None  # null when status='missing'
    notes: str = ""


class RankedJob(BaseModel):
    job_id: str
    overall_score: float = Field(..., ge=0.0, le=1.0)
    criteria: list[Criterion] = Field(default_factory=list)
    reasoning_summary: str = ""


class RankedJobList(BaseModel):
    """Ranker agent's aggregated output per PRD §3 T3.

    ranked_jobs is sorted by overall_score descending with deterministic
    tie-breaks on equal scores (job_id ascending) per PRD §4 F-4.
    skipped_job_ids captures any ParsedJobs that were degraded upstream
    so the UI can note them rather than dropping them silently.
    """

    ranked_jobs: list[RankedJob] = Field(default_factory=list)
    skipped_job_ids: list[str] = Field(default_factory=list)


class CoachEdit(BaseModel):
    """A proposed rewrite of existing resume content.

    INVARIANT (SAD §4, PRD §4 F-5): evidence_span is non-nullable.
    An edit without verbatim resume evidence is schema-invalid and is
    dropped before the plan is returned to the Coach agent.
    """

    id: str
    target_section: TargetSection
    target_span: Span  # existing resume content being edited (verbatim)
    suggested_text: str
    evidence_span: Span  # REQUIRED; non-null by schema
    rationale: str = ""


class CoachGap(BaseModel):
    """A skill or qualification the candidate lacks for the selected role.

    Never merged into CoachEdit — the separation is the product.
    """

    skill: str
    why_it_matters: str
    learn_path_hint: Optional[str] = None


class CoachPlan(BaseModel):
    """Coach agent's per-role output per PRD §3 T4."""

    job_id: str
    edits: list[CoachEdit] = Field(default_factory=list)
    gaps: list[CoachGap] = Field(default_factory=list)
