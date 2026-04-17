"""Job feed fetcher tool.

Used by the Sourcing agent per PRD §3 and SAD §2. Fetches tech job postings
from the current "Ask HN: Who is hiring?" thread on Hacker News via the
public Firebase API, applies a lightweight keyword filter derived from the
candidate's career-intent prompt, and returns a JSON shortlist.

Source allowlist (SAD §4) is enforced at the HTTP layer: any URL whose host
is not in ALLOWED_HOSTS raises before a request is issued.
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

HN_ITEM_URL_TMPL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
HN_USER_URL = "https://hacker-news.firebaseio.com/v0/user/whoishiring.json"
HN_COMMENT_URL_TMPL = "https://news.ycombinator.com/item?id={id}"

ALLOWED_HOSTS = frozenset(
    {
        "hacker-news.firebaseio.com",
        "news.ycombinator.com",
    }
)

SOURCE_ID = "hn_whos_hiring"
HIRING_THREAD_TITLE_PREFIX = "ask hn: who is hiring?"

DEFAULT_LIMIT = 20
MIN_FILTERED = 5
REQUEST_TIMEOUT_SEC = 10
MAX_WHOISHIRING_SCAN = 30

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


class JobFeedFetcherInput(BaseModel):
    """Input schema for JobFeedFetcherTool."""

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


class JobFeedFetcherTool(BaseTool):
    name: str = "job_feed_fetcher"
    description: str = (
        "Fetch a shortlist of open tech job postings from the current "
        "'Ask HN: Who is hiring?' thread on Hacker News. "
        "Input: the candidate's intent prompt and an optional limit. "
        "Output: a JSON string with 'status' and a 'jobs' list. "
        "Each job has id, title, company, location, url, source, and raw_description."
    )
    args_schema: Type[BaseModel] = JobFeedFetcherInput

    def _run(self, intent_prompt: str, limit: int = DEFAULT_LIMIT) -> str:
        try:
            thread_id = self._find_current_hiring_thread_id()
        except (URLError, ValueError, TimeoutError) as e:
            logger.warning("job_feed_fetcher: lookup failed: %s", e)
            return _degraded("Could not locate the current HN 'Who is hiring?' thread.")

        if thread_id is None:
            return _degraded("No current HN 'Who is hiring?' thread found in recent submissions.")

        try:
            thread = self._fetch_item(thread_id)
        except (URLError, TimeoutError) as e:
            logger.warning("job_feed_fetcher: thread fetch failed for %s: %s", thread_id, e)
            return _degraded(f"Failed to fetch HN thread {thread_id}.")

        if not thread:
            return _degraded(f"HN thread {thread_id} returned empty.")

        comment_ids = thread.get("kids") or []
        if not comment_ids:
            return _degraded("HN hiring thread has no top-level job posts yet.")

        candidates: list[dict[str, Any]] = []
        for cid in comment_ids:
            try:
                item = self._fetch_item(cid)
            except (URLError, TimeoutError):
                continue
            if not item or item.get("deleted") or item.get("dead"):
                continue
            job = _normalize_comment(item)
            if job is not None:
                candidates.append(job)

        keywords = extract_keywords(intent_prompt)
        filtered = filter_by_keywords(candidates, keywords)

        if len(filtered) >= MIN_FILTERED:
            jobs = filtered[:limit]
            status = "ok"
        elif candidates:
            jobs = candidates[:limit]
            status = "ok_unfiltered"
        else:
            return _degraded("HN thread yielded no parseable job posts.")

        return json.dumps(
            {
                "status": status,
                "source": SOURCE_ID,
                "thread_id": thread_id,
                "keywords_used": keywords,
                "count": len(jobs),
                "jobs": jobs,
            },
            ensure_ascii=False,
        )

    def _fetch_item(self, item_id: int) -> dict[str, Any] | None:
        data = _http_get_json(HN_ITEM_URL_TMPL.format(id=item_id))
        return data if isinstance(data, dict) else None

    def _find_current_hiring_thread_id(self) -> int | None:
        user = _http_get_json(HN_USER_URL)
        submitted = user.get("submitted", []) if isinstance(user, dict) else []
        for sid in submitted[:MAX_WHOISHIRING_SCAN]:
            item = self._fetch_item(sid)
            if not item:
                continue
            title = (item.get("title") or "").strip().lower()
            if title.startswith(HIRING_THREAD_TITLE_PREFIX):
                return int(sid)
        return None


def _http_get_json(url: str) -> Any:
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"Host not allowed by source allowlist: {parsed.hostname!r}")
    req = Request(url, headers={"User-Agent": "recruitment-assistant/0.1 (+bootcamp)"})
    with urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _strip_html(text: str) -> str:
    unescaped = html.unescape(text or "")
    no_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", no_tags).strip()


def _normalize_comment(item: dict[str, Any]) -> dict[str, Any] | None:
    raw_text = item.get("text") or ""
    cleaned = _strip_html(raw_text)
    if not cleaned:
        return None

    comment_id = int(item["id"])
    title, company, location = _parse_header(cleaned)
    url = HN_COMMENT_URL_TMPL.format(id=comment_id)
    job_id = hashlib.sha256(f"{SOURCE_ID}:{comment_id}".encode()).hexdigest()[:16]

    return {
        "id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "source": SOURCE_ID,
        "raw_description": cleaned,
    }


def _parse_header(text: str) -> tuple[str, str, str | None]:
    first_line = text.split("\n", 1)[0]
    first_line = first_line.split(". ", 1)[0]
    parts = [p.strip() for p in first_line.split("|")]
    if len(parts) >= 2 and all(parts[:2]):
        company = parts[0]
        title = parts[1]
        location = parts[2] if len(parts) >= 3 and parts[2] else None
    else:
        company = ""
        title = first_line[:200]
        location = None
    return title, company, location


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
