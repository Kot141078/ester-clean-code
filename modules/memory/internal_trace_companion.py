# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
from collections import Counter
from typing import Any, Dict, List

from modules.memory.diagnostic_io import write_json, write_text
from modules.memory.reply_trace import history_rows
from modules.memory.trace_reasoning_trend import compute_reasoning_trend


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


def companion_path() -> str:
    return os.path.join(_diag_dir(), "companion.json")


def companion_digest_path() -> str:
    return os.path.join(_diag_dir(), "companion.md")


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    write_json(path, payload)


def _write_text(path: str, text: str) -> None:
    write_text(path, text)


def _render_markdown(payload: Dict[str, Any]) -> str:
    latest = dict(payload.get("latest") or {})
    trend = dict(payload.get("trend") or {})
    lines = [
        "# internal trace companion",
        "",
        f"- points_total: {int(payload.get('points_total') or 0)}",
        f"- users_total: {int(payload.get('users_total') or 0)}",
        f"- chats_total: {int(payload.get('chats_total') or 0)}",
        f"- dominant_bias_label: {str(payload.get('dominant_bias_label') or '')}",
        f"- dominant_reply_mode: {str(payload.get('dominant_reply_mode') or '')}",
        f"- trend_label: {str(trend.get('label') or '')}",
        "",
        f"- latest_mode: {str(latest.get('reply_mode') or '')}",
        f"- latest_bias: {str(latest.get('reasoning_bias_label') or '')}",
        f"- latest_priority: {str(latest.get('capture_priority_label') or '')}",
        "",
        "_c=a+b_",
    ]
    return "\n".join(lines).strip() + "\n"


def ensure_materialized(limit: int = 120) -> Dict[str, Any]:
    rows = history_rows(limit=limit)
    now_ts = int(time.time())
    if not rows:
        payload = {
            "schema": "ester.internal_trace.companion.v1",
            "generated_ts": now_ts,
            "points_total": 0,
            "users_total": 0,
            "chats_total": 0,
            "dominant_bias_label": "",
            "dominant_reply_mode": "",
            "latest": {},
            "trend": compute_reasoning_trend([]),
        }
        _write_json(companion_path(), payload)
        _write_text(companion_digest_path(), _render_markdown(payload))
        return payload

    latest = dict(rows[-1] or {})
    bias_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    users = set()
    chats = set()
    for row in rows:
        bias = str((dict(row.get("reasoning_bias") or {})).get("label") or "").strip()
        mode = str(row.get("reply_mode") or "").strip()
        if bias:
            bias_counts[bias] += 1
        if mode:
            mode_counts[mode] += 1
        user_id = str(row.get("user_id") or "").strip()
        chat_id = str(row.get("chat_id") or "").strip()
        if user_id:
            users.add(user_id)
        if chat_id:
            chats.add(chat_id)

    trend = compute_reasoning_trend(rows[-24:])
    payload = {
        "schema": "ester.internal_trace.companion.v1",
        "generated_ts": now_ts,
        "points_total": len(rows),
        "users_total": len(users),
        "chats_total": len(chats),
        "dominant_bias_label": (bias_counts.most_common(1) or [["", 0]])[0][0],
        "dominant_reply_mode": (mode_counts.most_common(1) or [["", 0]])[0][0],
        "latest": {
            "reply_mode": str(latest.get("reply_mode") or ""),
            "query": str(latest.get("query") or ""),
            "reply_preview": str(latest.get("reply_preview") or ""),
            "reasoning_bias_label": str((dict(latest.get("reasoning_bias") or {})).get("label") or ""),
            "capture_priority_label": str((dict(latest.get("capture_priority") or {})).get("label") or ""),
            "capture_pressure_label": str((dict(latest.get("capture_pressure") or {})).get("label") or ""),
            "contour_stage_count": int((dict(latest.get("contour") or {})).get("stage_count") or 0),
        },
        "trend": trend,
        "bias_rollup": dict(bias_counts),
        "reply_mode_rollup": dict(mode_counts),
    }
    _write_json(companion_path(), payload)
    _write_text(companion_digest_path(), _render_markdown(payload))
    return payload


__all__ = ["companion_digest_path", "companion_path", "ensure_materialized"]
