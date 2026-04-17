"""Shared filter utilities for job-source tools.

Keeps keyword extraction and filtering in one place so job_feed_fetcher
and demo_corpus_reader apply the same rules to candidate jobs.
"""

from __future__ import annotations

import re
from typing import Any


_KEYWORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.-]{1,}")

STOP_WORDS = frozenset(
    {
        "a", "an", "and", "any", "are", "as", "at", "be", "by", "for",
        "from", "i", "in", "is", "it", "me", "my", "of", "on", "or",
        "the", "to", "with", "you", "your",
        "role", "roles", "job", "jobs", "looking", "seeking",
    }
)


def extract_keywords(intent_prompt: str) -> list[str]:
    """Tokenize an intent prompt into a filter-keyword list."""
    tokens = _KEYWORD_RE.findall(intent_prompt.lower())
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 2]


def filter_by_keywords(
    jobs: list[dict[str, Any]], keywords: list[str]
) -> list[dict[str, Any]]:
    """Return jobs whose title or raw_description contains any keyword."""
    if not keywords:
        return list(jobs)
    out: list[dict[str, Any]] = []
    for job in jobs:
        hay = f"{job.get('title', '')} {job.get('raw_description', '')}".lower()
        if any(kw in hay for kw in keywords):
            out.append(job)
    return out
