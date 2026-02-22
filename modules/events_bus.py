# -*- coding: utf-8 -*-
"""
modules.events_bus — lightweight events bus (in-memory + append-only NDJSON).

Supported API:
- append(kind, payload=None, **meta) -> event dict
- publish(kind, payload=None, meta=None, **extra) -> {ok, event}
- feed(since=0.0, kind=None, limit=100, kinds=None) -> list or {ok,items,count}
- last_ts() -> float
- count(), clear()
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

_MAX_INMEM = 10_000
_lock = threading.RLock()
_feed: List[Dict[str, Any]] = []
_scope_key: Optional[str] = None


def _persist_dir() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    path = os.path.join(base, "events")
    os.makedirs(path, exist_ok=True)
    return path


def _events_path() -> str:
    return os.path.join(_persist_dir(), "events.ndjson")


def _ensure_scope_locked() -> None:
    """Reset in-memory buffer when storage scope (PERSIST_DIR) changes."""
    global _scope_key
    key = _events_path()
    if _scope_key is None:
        _scope_key = key
        return
    if key != _scope_key:
        _feed.clear()
        _scope_key = key


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def _new_id() -> str:
    return f"evt_{uuid.uuid4().hex[:12]}"


def _append_inmem(rec: Dict[str, Any]) -> None:
    _feed.append(rec)
    if len(_feed) > _MAX_INMEM:
        del _feed[: len(_feed) - _MAX_INMEM]


def _append_file(rec: Dict[str, Any]) -> None:
    try:
        with open(_events_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def append(kind: str, payload: Any = None, **meta: Any) -> Dict[str, Any]:
    rec = {
        "id": _new_id(),
        "ts": float(time.time()),
        "kind": str(kind or "event"),
        "payload": payload,
    }
    if meta:
        rec["meta"] = dict(meta)
    with _lock:
        _ensure_scope_locked()
        _append_inmem(rec)
        _append_file(rec)
    return rec


def publish(kind: str, payload: Any = None, meta: Optional[Dict[str, Any]] = None, **extra: Any) -> Dict[str, Any]:
    extra_meta: Dict[str, Any] = {}
    if isinstance(meta, dict):
        extra_meta.update(meta)
    if extra:
        extra_meta.update(extra)
    rec = append(kind, payload, **extra_meta)
    return {"ok": True, "event": rec}


def _filter_items(
    items: List[Dict[str, Any]],
    since: float = 0.0,
    kind: Optional[str] = None,
    kinds: Optional[List[str]] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    since_f = _safe_float(since, 0.0)
    wanted_kind = str(kind).strip() if kind else ""
    wanted_kinds = {str(k).strip() for k in (kinds or []) if str(k).strip()}

    out: List[Dict[str, Any]] = []
    for it in items:
        ts = _safe_float(it.get("ts"), 0.0)
        if ts <= since_f:
            continue
        k = str(it.get("kind") or "")
        if wanted_kind and k != wanted_kind:
            continue
        if wanted_kinds and k not in wanted_kinds:
            continue
        out.append(it)
    if limit <= 0:
        limit = 1
    return out[-int(limit) :]


def feed(
    since: float = 0.0,
    kind: Optional[str] = None,
    limit: int = 100,
    kinds: Optional[List[str]] = None,
):
    """
    Compatibility mode:
    - when `kinds` is passed (even []), return dict for HTTP routes: {ok,items,count}
    - otherwise return bare list for legacy unit tests.
    """
    limit_i = max(1, min(int(limit or 100), _MAX_INMEM))
    with _lock:
        _ensure_scope_locked()
        items = list(_feed)
    filtered = _filter_items(items, since=since, kind=kind, kinds=kinds, limit=limit_i)

    if kinds is not None:
        return {"ok": True, "items": filtered, "count": len(filtered)}
    return filtered


def last_ts() -> float:
    with _lock:
        _ensure_scope_locked()
        if not _feed:
            return 0.0
        return _safe_float(_feed[-1].get("ts"), 0.0)


def count() -> int:
    with _lock:
        _ensure_scope_locked()
        return len(_feed)


def clear() -> Dict[str, Any]:
    with _lock:
        _ensure_scope_locked()
        _feed.clear()
    return {"ok": True, "cleared": True}


__all__ = [
    "append",
    "publish",
    "feed",
    "last_ts",
    "count",
    "clear",
]
