# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Iterable, List


def compute_reasoning_trend(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    points: List[Dict[str, Any]] = [dict(item or {}) for item in rows if isinstance(item, dict)]
    if not points:
        return {
            "schema": "ester.trace.reasoning_trend.v1",
            "label": "missing",
            "grounded_share": 0.0,
            "points_total": 0,
        }
    if len(points) == 1:
        first_bias = str((dict(points[0].get("reasoning_bias") or {})).get("label") or "")
        return {
            "schema": "ester.trace.reasoning_trend.v1",
            "label": "initial",
            "grounded_share": 1.0 if first_bias in {"memory_grounded", "mixed_grounded", "file_led"} else 0.0,
            "points_total": 1,
        }

    def _grounded(row: Dict[str, Any]) -> int:
        bias = str((dict(row.get("reasoning_bias") or {})).get("label") or "").strip().lower()
        return 1 if bias in {"memory_grounded", "mixed_grounded", "file_led"} else 0

    midpoint = max(1, len(points) // 2)
    older = points[:midpoint]
    newer = points[midpoint:]
    older_share = sum(_grounded(item) for item in older) / max(1, len(older))
    newer_share = sum(_grounded(item) for item in newer) / max(1, len(newer))

    label = "mixed"
    if newer_share >= older_share + 0.25:
        label = "grounding_improving"
    elif newer_share <= older_share - 0.25:
        label = "grounding_thinning"
    elif newer_share >= 0.75:
        label = "grounding_stable"

    return {
        "schema": "ester.trace.reasoning_trend.v1",
        "label": label,
        "points_total": len(points),
        "grounded_share": round(newer_share, 3),
        "older_grounded_share": round(older_share, 3),
        "newer_grounded_share": round(newer_share, 3),
    }


__all__ = ["compute_reasoning_trend"]
