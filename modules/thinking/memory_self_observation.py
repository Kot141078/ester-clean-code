# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Dict, Optional


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def is_memory_self_query(text: str) -> bool:
    q = _normalize_text(text)
    markers = (
        "что ты помнишь",
        "как у тебя с памятью",
        "насколько ты помнишь",
        "что у тебя в памяти",
        "помнишь ли ты",
        "свою память",
        "своей памяти",
        "memory",
        "trace",
        "диагностик",
    )
    return any(marker in q for marker in markers)


def build_memory_self_observation(
    query: str,
    *,
    diagnostics: Optional[Dict[str, Any]] = None,
    max_chars: int = 1200,
) -> str:
    if not is_memory_self_query(query):
        return ""
    report = dict(diagnostics or {})
    if not report:
        try:
            from modules.memory import self_diagnostics  # type: ignore

            report = dict((self_diagnostics.latest() or {}).get("report") or {})
        except Exception:
            report = {}
    if not report:
        return "[MEMORY_SELF]\n- явные self-diagnostics по памяти пока не materialized."

    lines = [
        "[MEMORY_SELF]",
        f"- status: {str(report.get('status_label') or '')}",
        f"- introspection: {str(report.get('introspection_label') or '')}",
        f"- honesty: {str(report.get('honesty_label') or '')}",
        f"- trace_mode: {str(report.get('trace_mode') or '')}",
        f"- trace_bias: {str(report.get('trace_bias_label') or '')}",
        f"- trace_coverage: {str(report.get('trace_coverage_label') or '')}",
    ]
    for note in list(report.get("top_notes") or [])[:3]:
        note_text = str(note or "").strip()
        if note_text:
            lines.append(f"- note: {note_text}")
    out = "\n".join(lines).strip()
    if len(out) <= max_chars:
        return out
    return out[: max_chars - 1].rstrip() + "…"


__all__ = ["build_memory_self_observation", "is_memory_self_query"]
