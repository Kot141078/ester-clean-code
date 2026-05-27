# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from types import ModuleType
from typing import Any, Dict, Iterable, List, Optional

from .bus import MemoryBus
from .journal import record_event


def _install_events_compat() -> ModuleType:
    module_name = f"{__name__}.events"
    module = sys.modules.get(module_name)
    if module is None:
        module = ModuleType(module_name)
        sys.modules[module_name] = module
    if not callable(getattr(module, "record_event", None)):
        module.record_event = record_event  # type: ignore[attr-defined]
    return module


events = _install_events_compat()


def _install_memory_bus_compat() -> ModuleType:
    module_name = f"{__name__}.memory_bus"
    module = sys.modules.get(module_name)
    if module is None:
        module = ModuleType(module_name)
        sys.modules[module_name] = module
    if not callable(getattr(module, "MemoryBus", None)):
        module.MemoryBus = MemoryBus  # type: ignore[attr-defined]
    return module


memory_bus = _install_memory_bus_compat()


def _record_ts(rec: Dict[str, Any]) -> int:
    try:
        return int(float(rec.get("ts") or rec.get("mtime") or rec.get("time") or rec.get("timestamp") or 0))
    except Exception:
        return 0


def _record_source(rec: Dict[str, Any]) -> str:
    meta = rec.get("meta")
    if isinstance(meta, dict):
        source = str(meta.get("source") or "").strip()
        if source:
            return source
    return str(rec.get("source") or "").strip()


def _timeline_matches(
    rec: Dict[str, Any],
    *,
    start_ts: Optional[int],
    end_ts: Optional[int],
    type_: Optional[str],
    source: Optional[str],
    q: Optional[str],
) -> bool:
    ts = _record_ts(rec)
    if start_ts is not None and ts < int(start_ts):
        return False
    if end_ts is not None and ts > int(end_ts):
        return False
    if type_ is not None and str(rec.get("type") or rec.get("kind") or "") != str(type_):
        return False
    if source is not None and _record_source(rec) != str(source):
        return False
    if q:
        needle = str(q).lower()
        haystack = " ".join(
            [
                str(rec.get("id") or ""),
                str(rec.get("type") or rec.get("kind") or ""),
                str(rec.get("text") or rec.get("content") or ""),
                _record_source(rec),
            ]
        ).lower()
        if needle not in haystack:
            return False
    return True


def _coerce_non_negative(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(0, parsed)


def _build_timeline(
    *,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    type_: Optional[str] = None,
    source: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    from modules.memory import store

    try:
        rows: Iterable[Dict[str, Any]] = store.items()
    except Exception as e:
        return {"ok": False, "error": f"timeline_unavailable: {e}", "items": [], "timeline": [], "total": 0}

    filtered: List[Dict[str, Any]] = [
        dict(rec)
        for rec in rows
        if isinstance(rec, dict)
        and _timeline_matches(rec, start_ts=start_ts, end_ts=end_ts, type_=type_, source=source, q=q)
    ]
    filtered.sort(key=_record_ts, reverse=True)

    offset_i = _coerce_non_negative(offset, 0)
    limit_i = _coerce_non_negative(limit, 100)
    page = filtered[offset_i:] if limit_i == 0 else filtered[offset_i : offset_i + limit_i]
    return {"ok": True, "items": page, "timeline": page, "total": len(filtered), "limit": limit_i, "offset": offset_i}


def _install_timeline_compat() -> ModuleType:
    module_name = f"{__name__}.timeline"
    module = sys.modules.get(module_name)
    if module is None:
        module = ModuleType(module_name)
        sys.modules[module_name] = module
    if not callable(getattr(module, "build_timeline", None)):
        module.build_timeline = _build_timeline  # type: ignore[attr-defined]
    return module


timeline = _install_timeline_compat()

__all__ = ["events", "MemoryBus", "memory_bus", "timeline"]
