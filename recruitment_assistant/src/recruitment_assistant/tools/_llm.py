"""Shared LLM helpers for schema-constrained extraction / ranking / coaching tools.

Single configuration point for model routing and JSON-response parsing
so extract / rank / coach tools all behave the same way.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from crewai import LLM


DEFAULT_MODEL_FALLBACK = "anthropic/claude-sonnet-4-6"


def llm_complete(
    messages: list[dict[str, str]], temperature: float = 0.0
) -> str:
    """Call the configured LLM and return the assistant's text content."""
    model = os.environ.get("MODEL") or DEFAULT_MODEL_FALLBACK
    llm = LLM(model=model, temperature=temperature)
    return llm.call(messages=messages)


def parse_json_object(
    text: str,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Best-effort parse of an LLM response as a JSON object.

    Strips markdown fences if present. Returns (data, None) on success
    or (None, error_reason) on failure.
    """
    if not text:
        return None, "empty response"
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        nl = s.find("\n")
        if nl != -1 and s[:nl].strip().lower() in {"json", ""}:
            s = s[nl + 1 :]
        s = s.strip()
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        return None, f"json decode error: {e}"
    if not isinstance(data, dict):
        return None, "response was not a JSON object"
    return data, None
