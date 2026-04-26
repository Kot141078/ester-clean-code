# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict


def compute_reasoning_bias(
    *,
    active_memory_stats: Dict[str, Any] | None = None,
    provenance_count: int = 0,
    has_web: bool = False,
    has_file: bool = False,
    has_daily: bool = False,
    history_turns_used: int = 0,
) -> Dict[str, Any]:
    stats = dict(active_memory_stats or {})
    has_retrieval = bool(stats.get("has_retrieval"))
    has_recent_doc = bool(stats.get("has_recent_doc"))
    has_profile = bool(stats.get("has_profile")) or int(stats.get("facts_count") or 0) > 0

    label = "minimal_context"
    reasons = []

    if (has_retrieval or has_recent_doc or provenance_count > 0) and (has_web or has_file):
        label = "mixed_grounded"
        reasons.append("multi_source_grounding")
    elif has_recent_doc or has_file:
        label = "file_led"
        reasons.append("file_context")
    elif has_web:
        label = "web_led"
        reasons.append("web_context")
    elif has_retrieval or provenance_count > 0:
        label = "memory_grounded"
        reasons.append("retrieval_grounding")
    elif has_profile or int(history_turns_used or 0) >= 5:
        label = "history_led"
        reasons.append("history_context")
    elif has_daily:
        label = "daily_led"
        reasons.append("daily_context")

    return {
        "schema": "ester.trace.reasoning_bias.v1",
        "label": label,
        "reasons": reasons,
        "signals": {
            "has_retrieval": has_retrieval,
            "has_recent_doc": has_recent_doc,
            "provenance_count": int(provenance_count or 0),
            "has_web": bool(has_web),
            "has_file": bool(has_file),
            "has_daily": bool(has_daily),
            "history_turns_used": int(history_turns_used or 0),
        },
    }


__all__ = ["compute_reasoning_bias"]
