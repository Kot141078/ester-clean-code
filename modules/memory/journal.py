# -*- coding: utf-8 -*-
"""In-process compatibility journal for the clean-code skeleton.

The module keeps entries in memory only. It does not create runtime journal
files, read private memory, or call external services.
"""

from __future__ import annotations

import time
from typing import Any

_ROWS: list[dict[str, Any]] = []


def _next_id() -> str:
    return f"journal-{len(_ROWS) + 1}"


def record_event(
    kind: str = "event",
    op: str = "",
    *,
    ok: bool = True,
    info: dict[str, Any] | None = None,
    result: Any = None,
    source: str = "memory_journal",
    trace_id: str = "",
    **extra: Any,
) -> dict[str, Any]:
    payload = dict(info or {})
    if result is not None:
        payload["result"] = result
    if op:
        payload["op"] = str(op)
    if trace_id:
        payload["trace_id"] = str(trace_id)
    if extra:
        payload.update(extra)

    row = {
        "id": _next_id(),
        "ts": int(time.time()),
        "kind": str(kind or "event"),
        "source": str(source or "memory_journal"),
        "payload": payload,
        "ok": bool(ok),
        "error": "",
    }
    _ROWS.append(row)
    return dict(row)


def record_dream(text: str = "", *, meta: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    payload = dict(meta or {})
    if text:
        payload["text"] = str(text)
    if extra:
        payload.update(extra)
    row = record_event("dream", "record_dream", info=payload, source="memory_dream")
    return {"ok": True, "status": "recorded", "mode": "in_memory", "event": row}


def read_tail(limit: int = 100) -> list[dict[str, Any]]:
    try:
        n = max(1, int(limit))
    except Exception:
        n = 100
    return [dict(row) for row in _ROWS[-n:]]


def status() -> dict[str, Any]:
    return {"ok": True, "mode": "in_memory", "count": len(_ROWS)}


__all__ = ["read_tail", "record_dream", "record_event", "status"]
