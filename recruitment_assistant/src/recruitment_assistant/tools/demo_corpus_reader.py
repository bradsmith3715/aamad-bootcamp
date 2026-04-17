"""Demo corpus reader tool.

Used by the Sourcing agent per PRD §3 and SAD §6 as the reproducible
fallback source when the live feed is unavailable, restricted, or
explicitly bypassed for demo purposes.

The corpus is bundled as a package resource at
`recruitment_assistant/data/demo_corpus.json` so it travels with the
package and does not depend on a specific install layout.
"""

from __future__ import annotations

import hashlib
import json
import logging
from importlib.resources import files
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from recruitment_assistant.tools._filters import (
    extract_keywords,
    filter_by_keywords,
)


logger = logging.getLogger(__name__)

SOURCE_ID = "demo_corpus"
CORPUS_PACKAGE = "recruitment_assistant.data"
CORPUS_FILENAME = "demo_corpus.json"

DEFAULT_LIMIT = 20
MIN_FILTERED = 5


class DemoCorpusReaderInput(BaseModel):
    """Input schema for DemoCorpusReaderTool."""

    intent_prompt: str = Field(
        ...,
        description="Candidate's short career-intent prompt. Used to derive filter keywords.",
    )
    limit: int = Field(
        DEFAULT_LIMIT,
        ge=5,
        le=50,
        description="Maximum number of jobs to return.",
    )


class DemoCorpusReaderTool(BaseTool):
    name: str = "demo_corpus_reader"
    description: str = (
        "Return a shortlist of tech jobs from the seeded local demo corpus. "
        "Use this as a fallback when the live feed is unavailable or when "
        "reproducible demo results are needed. "
        "Input: the candidate's intent prompt and an optional limit. "
        "Output: a JSON string with 'status' and a 'jobs' list. "
        "Each job has id, title, company, location, url, source, and raw_description."
    )
    args_schema: Type[BaseModel] = DemoCorpusReaderInput

    def _run(self, intent_prompt: str, limit: int = DEFAULT_LIMIT) -> str:
        try:
            raw_entries = _load_corpus()
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            logger.warning("demo_corpus_reader: failed to load corpus: %s", e)
            return _degraded(f"Failed to load demo corpus: {e}")

        candidates = [job for job in (_normalize_entry(e) for e in raw_entries) if job]
        if not candidates:
            return _degraded("Demo corpus is empty or all entries are malformed.")

        keywords = extract_keywords(intent_prompt)
        filtered = filter_by_keywords(candidates, keywords)

        if len(filtered) >= MIN_FILTERED:
            jobs = filtered[:limit]
            status = "ok"
        else:
            jobs = candidates[:limit]
            status = "ok_unfiltered"

        return json.dumps(
            {
                "status": status,
                "source": SOURCE_ID,
                "keywords_used": keywords,
                "count": len(jobs),
                "jobs": jobs,
            },
            ensure_ascii=False,
        )


def _load_corpus() -> list[dict[str, Any]]:
    resource = files(CORPUS_PACKAGE).joinpath(CORPUS_FILENAME)
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "jobs" not in payload:
        raise ValueError("Corpus JSON missing top-level 'jobs' array.")
    jobs = payload["jobs"]
    if not isinstance(jobs, list):
        raise ValueError("Corpus 'jobs' is not a list.")
    return jobs


def _normalize_entry(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    slug = entry.get("slug")
    title = entry.get("title")
    raw_description = entry.get("raw_description")
    if not slug or not title or not raw_description:
        return None

    job_id = hashlib.sha256(f"{SOURCE_ID}:{slug}".encode()).hexdigest()[:16]
    url = f"demo://{slug}"

    return {
        "id": job_id,
        "title": title,
        "company": entry.get("company") or "",
        "location": entry.get("location"),
        "url": url,
        "source": SOURCE_ID,
        "raw_description": raw_description,
    }


def _degraded(reason: str) -> str:
    return json.dumps(
        {
            "status": "degraded",
            "reason": reason,
            "source": SOURCE_ID,
            "jobs": [],
        },
        ensure_ascii=False,
    )
