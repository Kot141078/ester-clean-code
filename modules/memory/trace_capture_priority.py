# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List


def compute_capture_priority(
    *,
    reply_mode: str,
    stage_count: int,
    reply_chars: int,
    provenance_count: int,
    active_memory_stats: Dict[str, Any] | None = None,
    honesty_report: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    stats = dict(active_memory_stats or {})
    honesty = dict(honesty_report or {})
    reasons: List[str] = []
    score = 20

    if provenance_count > 0:
        score += 25
        reasons.append("has_provenance")
    if bool(stats.get("has_retrieval")):
        score += 15
        reasons.append("has_retrieval")
    if bool(stats.get("has_recent_doc")):
        score += 10
        reasons.append("has_recent_doc")
    if bool(stats.get("has_profile")) or int(stats.get("facts_count") or 0) > 0:
        score += 10
        reasons.append("has_user_memory")
    if stage_count >= 4:
        score += 12
        reasons.append("deep_contour")
    elif stage_count >= 2:
        score += 6
        reasons.append("multi_stage")
    if str(reply_mode or "").strip().lower() == "cascade":
        score += 6
        reasons.append("cascade_mode")
    if int(reply_chars or 0) >= 700:
        score += 6
        reasons.append("long_reply")

    honesty_label = str(honesty.get("label") or "").strip().lower()
    if honesty_label in {"uncertain", "missing"}:
        score += 12
        reasons.append(f"honesty_{honesty_label}")
    elif honesty_label == "mixed":
        score += 6
        reasons.append("honesty_mixed")

    score = max(0, min(100, int(score)))
    label = "low"
    if score >= 80:
        label = "critical"
    elif score >= 60:
        label = "high"
    elif score >= 35:
        label = "normal"

    return {
        "schema": "ester.trace.capture_priority.v1",
        "label": label,
        "score": score,
        "reasons": reasons,
    }


__all__ = ["compute_capture_priority"]
