# -*- coding: utf-8 -*-
"""Clean-code compatibility API for the memory experience layer.

This module is intentionally in-process only: it builds a small profile from
caller-provided insight dictionaries and never reads or writes runtime memory.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from typing import Any

_LAST_SLEEP_STATUS: dict[str, Any] = {}


def _slot() -> str:
    raw = str(os.getenv("ESTER_MEMORY_EXPERIENCE_AB", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _terms_from_text(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    stop = {
        "and",
        "are",
        "for",
        "from",
        "generally",
        "main",
        "the",
        "there",
        "today",
        "were",
        "with",
    }
    counts = Counter(word for word in words if word not in stop)
    return [word for word, _ in counts.most_common(12)]


def make_profile_from_insights(info: dict[str, Any] | None = None) -> dict[str, Any]:
    data = dict(info or {})
    insights = [item for item in data.get("insights", []) if isinstance(item, dict)]
    summary_text = _clean_text(data.get("summary_text") or data.get("summary"))

    sample: list[dict[str, str]] = []
    text_parts: list[str] = [summary_text] if summary_text else []
    for item in insights[:5]:
        title = _clean_text(item.get("title"))
        text = _clean_text(item.get("text") or item.get("summary"))
        if title or text:
            sample.append({"title": title, "text": text})
        text_parts.extend(part for part in (title, text) if part)

    return {
        "ok": True,
        "status": "skeleton",
        "slot": _slot(),
        "total_insights": len(insights),
        "top_terms": _terms_from_text(" ".join(text_parts)),
        "sample": sample,
        "summary_text": summary_text,
    }


def build_experience_profile(info: dict[str, Any] | None = None) -> dict[str, Any]:
    if info is not None:
        return make_profile_from_insights(info)
    return make_profile_from_insights({"insights": [], "summary_text": ""})


def get_experience_profile() -> dict[str, Any]:
    return build_experience_profile()


def set_last_sleep_status(result: dict[str, Any] | None) -> dict[str, Any]:
    global _LAST_SLEEP_STATUS
    _LAST_SLEEP_STATUS = dict(result or {})
    return {"ok": True, "stored": bool(_LAST_SLEEP_STATUS)}


def sync_experience(mode: str = "auto") -> dict[str, Any]:
    profile = build_experience_profile()
    return {"ok": True, "mode": str(mode or "auto"), "profile": profile, "synced": False}


__all__ = [
    "build_experience_profile",
    "get_experience_profile",
    "make_profile_from_insights",
    "set_last_sleep_status",
    "sync_experience",
]
