"""RemoteOK feed fetcher tool.

Alternative live-feed tool for the Sourcing agent. Fetches remote job
postings from the RemoteOK public API (https://remoteok.com/api),
applies the same intent-prompt keyword filter used by job_feed_fetcher,
and returns a JSON shortlist in the same shape so the Sourcing agent
and downstream pipeline can consume either tool's output interchangeably.

Source allowlist (SAD §4) is enforced at the HTTP layer: any URL whose
host is not in ALLOWED_HOSTS raises before a request is issued.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from typing import Any, Type
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from recruitment_assistant.tools._filters import (
    extract_keywords,
    filter_by_keywords,
)


logger = logging.getLogger(__name__)

REMOTEOK_FEED_URL = "https://remoteok.com/api"

ALLOWED_HOSTS = frozenset({"remoteok.com"})

SOURCE_ID = "remote_ok"

DEFAULT_LIMIT = 20
MIN_FILTERED = 5
REQUEST_TIMEOUT_SEC = 10

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


class RemoteOkFetcherInput(BaseModel):
    """Input schema for RemoteOkFetcherTool."""

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


class RemoteOkFetcherTool(BaseTool):
    name: str = "remote_ok_fetcher"
    description: str = (
        "Fetch a shortlist of open remote tech job postings from the "
        "RemoteOK public API. Input: the candidate's intent prompt and "
        "an optional limit. Output: a JSON string with 'status' and a "
        "'jobs' list. Each job has id, title, company, location, url, "
        "source, and raw_description - same shape as job_feed_fetcher."
    )
    args_schema: Type[BaseModel] = RemoteOkFetcherInput

    def _run(self, intent_prompt: str, limit: int = DEFAULT_LIMIT) -> str:
        try:
            data = _http_get_json(REMOTEOK_FEED_URL)
        except (URLError, ValueError, TimeoutError) as e:
            logger.warning("remote_ok_fetcher: fetch failed: %s", e)
            return _degraded(f"Failed to fetch RemoteOK feed: {e}")

        if not isinstance(data, list):
            return _degraded("RemoteOK feed returned unexpected shape.")

        candidates: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            job = _normalize_listing(item)
            if job is not None:
                candidates.append(job)

        if not candidates:
            return _degraded("RemoteOK feed yielded no parseable listings.")

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


def _http_get_json(url: str) -> Any:
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"Host not allowed by source allowlist: {parsed.hostname!r}")
    # RemoteOK returns 403 without a User-Agent.
    req = Request(url, headers={"User-Agent": "recruitment-assistant/0.1 (+bootcamp)"})
    with urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _strip_html(text: str) -> str:
    unescaped = html.unescape(text or "")
    no_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", no_tags).strip()


def _normalize_listing(item: dict[str, Any]) -> dict[str, Any] | None:
    # RemoteOK's first feed entry is a legal/metadata object with no
    # `position`; skip it and any malformed row.
    title = (item.get("position") or "").strip()
    if not title:
        return None

    raw_id = str(item.get("id", "")).strip()
    if not raw_id:
        return None

    company = (item.get("company") or "").strip()
    location = (item.get("location") or "").strip() or None
    url = (item.get("url") or item.get("apply_url") or "").strip()
    description = _strip_html(item.get("description") or "")

    if not description:
        tags = item.get("tags") or []
        if isinstance(tags, list) and tags:
            description = ", ".join(str(t) for t in tags)

    if not description:
        return None

    job_id = hashlib.sha256(f"{SOURCE_ID}:{raw_id}".encode()).hexdigest()[:16]

    return {
        "id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "source": SOURCE_ID,
        "raw_description": description,
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
