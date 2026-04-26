# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from modules.memory.reply_trace import history_rows


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def query_traces(
    query: str,
    *,
    limit: int = 8,
    user_id: Optional[Any] = None,
    chat_id: Optional[Any] = None,
    history_limit: int = 240,
) -> Dict[str, Any]:
    tokens = [item for item in _normalize_text(query).split() if item]
    rows = history_rows(limit=history_limit)
    out: List[Dict[str, Any]] = []
    user_key = str(user_id or "").strip()
    chat_key = str(chat_id or "").strip()

    for row in reversed(rows):
        if user_key and str(row.get("user_id") or "").strip() != user_key:
            continue
        if chat_key and str(row.get("chat_id") or "").strip() != chat_key:
            continue
        haystack = " ".join(
            [
                _normalize_text(row.get("query") or ""),
                _normalize_text(row.get("reply_preview") or ""),
                _normalize_text(row.get("profile_summary") or ""),
                _normalize_text((dict(row.get("reasoning_bias") or {})).get("label") or ""),
            ]
        )
        if not tokens:
            score = 1
        else:
            score = sum(1 for token in tokens if token in haystack)
            if score <= 0:
                continue
        out.append(
            {
                "ts": int(row.get("ts") or 0),
                "user_id": str(row.get("user_id") or ""),
                "chat_id": str(row.get("chat_id") or ""),
                "reply_mode": str(row.get("reply_mode") or ""),
                "query": str(row.get("query") or ""),
                "reply_preview": str(row.get("reply_preview") or ""),
                "reasoning_bias_label": str((dict(row.get("reasoning_bias") or {})).get("label") or ""),
                "capture_priority_label": str((dict(row.get("capture_priority") or {})).get("label") or ""),
                "score": score,
            }
        )
        if len(out) >= max(1, int(limit)):
            break

    return {
        "ok": True,
        "query": str(query or ""),
        "results_total": len(out),
        "results": out,
    }


__all__ = ["query_traces"]
