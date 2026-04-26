# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from modules.memory.diagnostic_io import write_json, write_text


def _state_root() -> str:
    root = (
        os.environ.get("ESTER_STATE_DIR")
        or os.environ.get("ESTER_HOME")
        or os.environ.get("ESTER_ROOT")
        or os.getcwd()
    ).strip()
    return root


def _diag_dir() -> str:
    return os.path.join(_state_root(), "data", "memory", "diagnostics", "self")


def latest_path() -> str:
    return os.path.join(_diag_dir(), "latest.json")


def latest_digest_path() -> str:
    return os.path.join(_diag_dir(), "latest.md")


def history_path() -> str:
    return os.path.join(_diag_dir(), "history.jsonl")


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    write_json(path, payload)


def _write_text(path: str, text: str) -> None:
    write_text(path, text)


def _append_jsonl(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# memory self diagnostics",
        "",
        f"- status: {str(payload.get('status_label') or '')}",
        f"- introspection_label: {str(payload.get('introspection_label') or '')}",
        f"- honesty_label: {str(payload.get('honesty_label') or '')}",
        f"- trace_mode: {str(payload.get('trace_mode') or '')}",
        f"- trace_bias_label: {str(payload.get('trace_bias_label') or '')}",
        f"- trace_coverage_label: {str(payload.get('trace_coverage_label') or '')}",
        "",
        "## top notes",
    ]
    notes = [str(item) for item in list(payload.get("top_notes") or []) if str(item).strip()]
    if notes:
        for note in notes:
            lines.append(f"- {note}")
    else:
        lines.append("- none")
    lines.extend(["", "_c=a+b_"])
    return "\n".join(lines).strip() + "\n"


def ensure_materialized() -> Dict[str, Any]:
    try:
        from modules.memory import internal_trace_companion  # type: ignore
        from modules.memory import internal_trace_coverage  # type: ignore
        from modules.memory import recall_diagnostics  # type: ignore
        from modules.memory import reply_trace  # type: ignore
    except Exception:
        return {}

    recall_latest = dict((recall_diagnostics.latest() or {}).get("report") or {})
    reply_latest = dict((reply_trace.latest() or {}).get("report") or {})
    companion = dict(internal_trace_companion.ensure_materialized() or {})
    coverage = dict(internal_trace_coverage.ensure_materialized() or {})
    now_ts = int(time.time())

    gaps: List[str] = []
    top_notes: List[str] = []
    if not recall_latest:
        gaps.append("recall_diagnostic_missing")
    if not reply_latest:
        gaps.append("reply_trace_missing")
    if str(coverage.get("coverage_label") or "") in {"low", "empty"}:
        gaps.append("trace_coverage_thin")

    honesty_label = str((dict(reply_latest.get("honesty") or {})).get("label") or "") or str(
        ((dict(recall_latest.get("sections") or {})).get("honesty") or "")
    )
    trace_mode = str(reply_latest.get("reply_mode") or "")
    trace_bias_label = str((dict(reply_latest.get("reasoning_bias") or {})).get("label") or "")
    coverage_label = str(coverage.get("coverage_label") or "")
    trend_label = str((dict(companion.get("trend") or {})).get("label") or "")

    if recall_latest and reply_latest:
        top_notes.append("active memory bundle and reply contour are both traceable")
    if trace_bias_label:
        top_notes.append(f"recent reasoning bias = {trace_bias_label}")
    if coverage_label:
        top_notes.append(f"internal trace coverage = {coverage_label}")
    if trend_label:
        top_notes.append(f"reasoning trend = {trend_label}")

    status = "instrumented"
    if gaps and len(gaps) >= 2:
        status = "partial"
    if not recall_latest and not reply_latest:
        status = "missing"

    introspection_label = "traceable"
    if status == "missing":
        introspection_label = "untraceable"
    elif gaps:
        introspection_label = "partially_traceable"

    payload = {
        "schema": "ester.memory.self_diagnostics.v1",
        "generated_ts": now_ts,
        "status_label": status,
        "introspection_label": introspection_label,
        "honesty_label": honesty_label,
        "trace_mode": trace_mode,
        "trace_bias_label": trace_bias_label,
        "trace_coverage_label": coverage_label,
        "reasoning_trend_label": trend_label,
        "reply_trace_latest_ts": int(reply_latest.get("ts") or 0),
        "recall_latest_ts": int(recall_latest.get("ts") or 0),
        "trace_priority_label": str((dict(reply_latest.get("capture_priority") or {})).get("label") or ""),
        "trace_pressure_label": str((dict(reply_latest.get("capture_pressure") or {})).get("label") or ""),
        "gaps": gaps,
        "top_notes": top_notes[:8],
        "coverage": {
            "profile_ratio": coverage.get("profile_ratio"),
            "honesty_ratio": coverage.get("honesty_ratio"),
            "provenance_ratio": coverage.get("provenance_ratio"),
            "multistage_ratio": coverage.get("multistage_ratio"),
        },
        "companion": {
            "dominant_bias_label": str(companion.get("dominant_bias_label") or ""),
            "dominant_reply_mode": str(companion.get("dominant_reply_mode") or ""),
            "points_total": int(companion.get("points_total") or 0),
        },
    }
    _write_json(latest_path(), payload)
    _write_text(latest_digest_path(), _render_markdown(payload))
    _append_jsonl(history_path(), payload)
    try:
        from modules.memory import memory_index  # type: ignore

        memory_index.ensure_materialized()
    except Exception:
        pass
    return payload


def latest() -> Dict[str, Any]:
    path = latest_path()
    if not os.path.exists(path):
        return {"ok": False, "error": "not_found"}
    report = _read_json(path)
    if report:
        return {"ok": True, "report": report}
    return {"ok": False, "error": "bad_payload"}


__all__ = ["ensure_materialized", "history_path", "latest", "latest_digest_path", "latest_path"]
