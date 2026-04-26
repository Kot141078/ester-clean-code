# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List


def compute_capture_pressure(
    *,
    query_chars: int,
    reply_chars: int,
    history_turns_used: int,
    stage_count: int,
    tool_rounds_total: int = 0,
) -> Dict[str, Any]:
    reasons: List[str] = []
    score = 10

    if int(query_chars or 0) >= 1200:
        score += 15
        reasons.append("long_query")
    elif int(query_chars or 0) >= 400:
        score += 8
        reasons.append("medium_query")

    if int(reply_chars or 0) >= 1200:
        score += 18
        reasons.append("long_reply")
    elif int(reply_chars or 0) >= 500:
        score += 10
        reasons.append("medium_reply")

    if int(history_turns_used or 0) >= 10:
        score += 14
        reasons.append("deep_history")
    elif int(history_turns_used or 0) >= 5:
        score += 7
        reasons.append("history_context")

    if int(stage_count or 0) >= 4:
        score += 12
        reasons.append("four_stage_contour")
    elif int(stage_count or 0) >= 2:
        score += 6
        reasons.append("multi_stage_contour")

    if int(tool_rounds_total or 0) > 0:
        score += min(15, int(tool_rounds_total) * 5)
        reasons.append("tool_roundtrip")

    score = max(0, min(100, int(score)))
    label = "light"
    if score >= 75:
        label = "high"
    elif score >= 45:
        label = "elevated"
    elif score >= 25:
        label = "watch"

    return {
        "schema": "ester.trace.capture_pressure.v1",
        "label": label,
        "score": score,
        "reasons": reasons,
    }


__all__ = ["compute_capture_pressure"]
