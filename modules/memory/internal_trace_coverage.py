# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
from typing import Any, Dict, List

from modules.memory.diagnostic_io import write_json, write_text
from modules.memory.reply_trace import history_rows


def _state_root() -> str:
    root = (
        os.environ.get("ESTER_STATE_DIR")
        or os.environ.get("ESTER_HOME")
        or os.environ.get("ESTER_ROOT")
        or os.getcwd()
    ).strip()
    return root


def _diag_dir() -> str:
    return os.path.join(_state_root(), "data", "memory", "diagnostics", "internal_trace")


def coverage_path() -> str:
    return os.path.join(_diag_dir(), "coverage.json")


def coverage_digest_path() -> str:
    return os.path.join(_diag_dir(), "coverage.md")


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    write_json(path, payload)


def _write_text(path: str, text: str) -> None:
    write_text(path, text)


def _ratio(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(float(value) / float(total), 3)


def _render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# internal trace coverage",
        "",
        f"- coverage_label: {str(payload.get('coverage_label') or '')}",
        f"- coverage_score: {int(payload.get('coverage_score') or 0)}",
        f"- points_total: {int(payload.get('points_total') or 0)}",
        f"- profile_ratio: {payload.get('profile_ratio')}",
        f"- honesty_ratio: {payload.get('honesty_ratio')}",
        f"- provenance_ratio: {payload.get('provenance_ratio')}",
        f"- multistage_ratio: {payload.get('multistage_ratio')}",
        "",
        "_c=a+b_",
    ]
    return "\n".join(lines).strip() + "\n"


def ensure_materialized(limit: int = 120) -> Dict[str, Any]:
    rows = history_rows(limit=limit)
    total = len(rows)
    if total <= 0:
        payload = {
            "schema": "ester.internal_trace.coverage.v1",
            "generated_ts": int(time.time()),
            "points_total": 0,
            "coverage_label": "empty",
            "coverage_score": 0,
            "gaps": ["trace_history_missing"],
            "profile_ratio": 0.0,
            "honesty_ratio": 0.0,
            "provenance_ratio": 0.0,
            "multistage_ratio": 0.0,
            "retrieval_ratio": 0.0,
            "recent_doc_ratio": 0.0,
        }
        _write_json(coverage_path(), payload)
        _write_text(coverage_digest_path(), _render_markdown(payload))
        return payload

    with_profile = 0
    with_honesty = 0
    with_provenance = 0
    multistage = 0
    with_retrieval = 0
    with_recent_doc = 0
    for row in rows:
        support = dict(row.get("memory_support") or {})
        honesty = dict(row.get("honesty") or {})
        contour = dict(row.get("contour") or {})
        if bool(support.get("has_profile")) or str(row.get("profile_summary") or "").strip():
            with_profile += 1
        if str(honesty.get("label") or "").strip():
            with_honesty += 1
        if int(support.get("provenance_count") or 0) > 0:
            with_provenance += 1
        if int(contour.get("stage_count") or 0) >= 2:
            multistage += 1
        if bool(support.get("has_retrieval")):
            with_retrieval += 1
        if bool(support.get("has_recent_doc")):
            with_recent_doc += 1

    profile_ratio = _ratio(with_profile, total)
    honesty_ratio = _ratio(with_honesty, total)
    provenance_ratio = _ratio(with_provenance, total)
    multistage_ratio = _ratio(multistage, total)
    retrieval_ratio = _ratio(with_retrieval, total)
    recent_doc_ratio = _ratio(with_recent_doc, total)
    score = int(round(((profile_ratio + honesty_ratio + provenance_ratio + multistage_ratio + retrieval_ratio + recent_doc_ratio) / 6.0) * 100))
    label = "low"
    if score >= 75:
        label = "high"
    elif score >= 45:
        label = "moderate"

    gaps: List[str] = []
    if profile_ratio < 0.5:
        gaps.append("profile_surface_thin")
    if honesty_ratio < 0.8:
        gaps.append("honesty_surface_thin")
    if multistage_ratio < 0.3:
        gaps.append("contour_surface_thin")
    if provenance_ratio < 0.2:
        gaps.append("provenance_surface_thin")

    payload = {
        "schema": "ester.internal_trace.coverage.v1",
        "generated_ts": int(time.time()),
        "points_total": total,
        "coverage_label": label,
        "coverage_score": score,
        "gaps": gaps,
        "profile_ratio": profile_ratio,
        "honesty_ratio": honesty_ratio,
        "provenance_ratio": provenance_ratio,
        "multistage_ratio": multistage_ratio,
        "retrieval_ratio": retrieval_ratio,
        "recent_doc_ratio": recent_doc_ratio,
    }
    _write_json(coverage_path(), payload)
    _write_text(coverage_digest_path(), _render_markdown(payload))
    return payload


__all__ = ["coverage_digest_path", "coverage_path", "ensure_materialized"]
