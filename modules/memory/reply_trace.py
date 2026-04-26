# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

from modules.memory.diagnostic_io import write_json, write_text
from modules.memory.trace_capture_pressure import compute_capture_pressure
from modules.memory.trace_capture_priority import compute_capture_priority
from modules.memory.trace_reasoning_bias import compute_reasoning_bias


def _state_root() -> str:
    root = (
        os.environ.get("ESTER_STATE_DIR")
        or os.environ.get("ESTER_HOME")
        or os.environ.get("ESTER_ROOT")
        or os.getcwd()
    ).strip()
    return root


def _diag_dir() -> str:
    return os.path.join(_state_root(), "data", "memory", "diagnostics", "reply_trace")


def latest_path() -> str:
    return os.path.join(_diag_dir(), "latest.json")


def history_path() -> str:
    return os.path.join(_diag_dir(), "history.jsonl")


def latest_digest_path() -> str:
    return os.path.join(_diag_dir(), "latest.md")


def _trim_text(value: Any, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    write_json(path, payload)


def _write_text(path: str, text: str) -> None:
    write_text(path, text)


def _append_jsonl(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _render_markdown(payload: Dict[str, Any]) -> str:
    contour = dict(payload.get("contour") or {})
    memory_support = dict(payload.get("memory_support") or {})
    priority = dict(payload.get("capture_priority") or {})
    pressure = dict(payload.get("capture_pressure") or {})
    bias = dict(payload.get("reasoning_bias") or {})
    lines = [
        "# memory reply trace",
        "",
        f"- mode: {str(payload.get('reply_mode') or '')}",
        f"- provider: {str(payload.get('provider') or '')}",
        f"- reply_chars: {int(payload.get('reply_chars') or 0)}",
        f"- contour_stage_count: {int(contour.get('stage_count') or 0)}",
        f"- capture_priority: {str(priority.get('label') or '')} ({int(priority.get('score') or 0)})",
        f"- capture_pressure: {str(pressure.get('label') or '')} ({int(pressure.get('score') or 0)})",
        f"- reasoning_bias: {str(bias.get('label') or '')}",
        f"- provenance_count: {int(memory_support.get('provenance_count') or 0)}",
        f"- query: {str(payload.get('query') or '')}",
        f"- reply_preview: {str(payload.get('reply_preview') or '')}",
        "",
        "_c=a+b_",
    ]
    return "\n".join(lines).strip() + "\n"


def _normalize_contour(trace: Optional[Dict[str, Any]], reply_mode: str, reply_text: str) -> Dict[str, Any]:
    payload = dict(trace or {})
    stages = dict(payload.get("stages") or {})
    order = [str(item).strip() for item in list(payload.get("stage_order") or []) if str(item).strip()]
    if not order:
        order = [str(key).strip() for key in stages.keys() if str(key).strip()]
    norm_stages: Dict[str, Any] = {}
    for stage_name in order:
        row = dict(stages.get(stage_name) or {})
        chars = int(row.get("chars") or 0)
        present = bool(row.get("present")) or chars > 0
        norm_stages[stage_name] = {
            "present": present,
            "chars": chars,
        }
    if not norm_stages:
        norm_stages = {
            str(reply_mode or "direct"): {
                "present": bool(str(reply_text or "").strip()),
                "chars": len(str(reply_text or "")),
            }
        }
        order = list(norm_stages.keys())
    return {
        "stage_order": order,
        "stage_count": len([item for item in norm_stages.values() if bool(item.get("present"))]),
        "stages": norm_stages,
    }


def _role_counts(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "").strip().lower()
        if role:
            counts[role] += 1
    return dict(counts)


def record_reply_trace(
    *,
    query: str,
    reply_text: str,
    user_id: Any,
    chat_id: Any,
    reply_mode: str,
    provider: str = "",
    trace: Optional[Dict[str, Any]] = None,
    active_memory_bundle: Optional[Dict[str, Any]] = None,
    profile_snapshot: Optional[Dict[str, Any]] = None,
    honesty_report: Optional[Dict[str, Any]] = None,
    provenance: Optional[Iterable[Dict[str, Any]]] = None,
    safe_history: Optional[List[Dict[str, Any]]] = None,
    has_web: bool = False,
    has_file: bool = False,
    has_daily: bool = False,
    tool_rounds_total: int = 0,
) -> Dict[str, Any]:
    ts = int(time.time())
    bundle = dict(active_memory_bundle or {})
    stats = dict(bundle.get("stats") or {})
    contour = _normalize_contour(trace, str(reply_mode or "").strip().lower() or "direct", reply_text)
    provenance_list = [dict(item) for item in (provenance or []) if isinstance(item, dict)]
    history_rows = [dict(item) for item in (safe_history or []) if isinstance(item, dict)]
    role_counts = _role_counts(history_rows)
    reply_chars = len(str(reply_text or ""))
    profile_summary = _trim_text((profile_snapshot or {}).get("summary") or "", 220)
    honesty = dict(honesty_report or {})

    priority = compute_capture_priority(
        reply_mode=str(reply_mode or ""),
        stage_count=int(contour.get("stage_count") or 0),
        reply_chars=reply_chars,
        provenance_count=len(provenance_list),
        active_memory_stats=stats,
        honesty_report=honesty,
    )
    pressure = compute_capture_pressure(
        query_chars=len(str(query or "")),
        reply_chars=reply_chars,
        history_turns_used=len(history_rows),
        stage_count=int(contour.get("stage_count") or 0),
        tool_rounds_total=int(tool_rounds_total or 0),
    )
    bias = compute_reasoning_bias(
        active_memory_stats=stats,
        provenance_count=len(provenance_list),
        has_web=bool(has_web),
        has_file=bool(has_file),
        has_daily=bool(has_daily),
        history_turns_used=len(history_rows),
    )

    payload = {
        "schema": "ester.reply_trace.v1",
        "ts": ts,
        "user_id": str(user_id or "").strip(),
        "chat_id": str(chat_id or "").strip(),
        "query": _trim_text(query, 500),
        "reply_preview": _trim_text(reply_text, 360),
        "reply_chars": reply_chars,
        "reply_mode": str(reply_mode or "").strip().lower() or "direct",
        "provider": str(provider or "").strip(),
        "tool_rounds_total": int(tool_rounds_total or 0),
        "contour": contour,
        "history": {
            "turns_used": len(history_rows),
            "role_counts": role_counts,
        },
        "memory_support": {
            "bundle_schema": str(bundle.get("schema") or ""),
            "context_chars": int(stats.get("context_chars") or 0),
            "sections_count": int(stats.get("sections_count") or 0),
            "facts_count": int(stats.get("facts_count") or 0),
            "recent_entries_count": int(stats.get("recent_entries_count") or 0),
            "has_profile": bool(stats.get("has_profile")),
            "has_honesty": bool(stats.get("has_honesty")),
            "has_recent_doc": bool(stats.get("has_recent_doc")),
            "has_retrieval": bool(stats.get("has_retrieval")),
            "has_people": bool(stats.get("has_people")),
            "has_daily": bool(stats.get("has_daily")),
            "has_web": bool(has_web),
            "has_file": bool(has_file),
            "has_daily_report": bool(has_daily),
            "provenance_count": len(provenance_list),
        },
        "profile_summary": profile_summary,
        "honesty": {
            "label": str(honesty.get("label") or "").strip(),
            "confidence": str(honesty.get("confidence") or "").strip(),
            "uncertainty_count": int(honesty.get("uncertainty_count") or 0),
            "provenance_count": int(honesty.get("provenance_count") or 0),
        },
        "provenance_preview": [
            {
                "doc_id": str(item.get("doc_id") or ""),
                "path": _trim_text(item.get("path") or "", 180),
                "page": item.get("page"),
                "offset": item.get("offset"),
            }
            for item in provenance_list[:6]
        ],
        "capture_priority": priority,
        "capture_pressure": pressure,
        "reasoning_bias": bias,
    }

    base = _diag_dir()
    stem = time.strftime("%Y%m%d_%H%M%S", time.localtime(ts))
    json_path = os.path.join(base, f"reply_trace_{stem}.json")
    _write_json(json_path, payload)
    _write_json(latest_path(), payload)
    _write_text(latest_digest_path(), _render_markdown(payload))
    _append_jsonl(history_path(), payload)

    try:
        from modules.memory import internal_trace_companion  # type: ignore

        internal_trace_companion.ensure_materialized()
    except Exception:
        pass
    try:
        from modules.memory import internal_trace_coverage  # type: ignore

        internal_trace_coverage.ensure_materialized()
    except Exception:
        pass
    try:
        from modules.memory import self_diagnostics  # type: ignore

        self_diagnostics.ensure_materialized()
    except Exception:
        pass
    try:
        from modules.memory import memory_index  # type: ignore

        memory_index.ensure_materialized()
    except Exception:
        pass
    return {
        "ok": True,
        "path": json_path,
        "latest_path": latest_path(),
        "history_path": history_path(),
        "report": payload,
    }


def latest() -> Dict[str, Any]:
    path = latest_path()
    if not os.path.exists(path):
        return {"ok": False, "error": "not_found"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if isinstance(data, dict):
            return {"ok": True, "report": data}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": False, "error": "bad_payload"}


def history_rows(limit: int = 120) -> List[Dict[str, Any]]:
    path = history_path()
    if not os.path.exists(path):
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                raw = str(line or "").strip()
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                except Exception:
                    continue
                if isinstance(parsed, dict):
                    rows.append(parsed)
    except Exception:
        return []
    return rows[-max(1, int(limit)) :]


__all__ = [
    "history_path",
    "history_rows",
    "latest",
    "latest_digest_path",
    "latest_path",
    "record_reply_trace",
]
