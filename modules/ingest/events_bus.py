# -*- coding: utf-8 -*-
"""
Local append-only JSONL events bus for ingest diagnostics.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional, Set

from modules.ingest.common import persist_dir


_LOCK = threading.RLock()


def _bus_path() -> str:
    root = os.path.join(persist_dir(), "ingest")
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, "events.jsonl")


def _normalize_kinds(kinds: Optional[Iterable[str] | str], kind: Optional[str] = None) -> Optional[Set[str]]:
    out: Set[str] = set()
    if kind:
        out.add(str(kind))
    if kinds is None:
        return out or None
    if isinstance(kinds, str):
        for k in kinds.split(","):
            k = k.strip()
            if k:
                out.add(k)
        return out or None
    for k in kinds:
        if k is not None:
            ks = str(k).strip()
            if ks:
                out.add(ks)
    return out or None


def emit(event_type: str, payload: Any, level: str = "info", meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rec = {
        "id": str(uuid.uuid4()),
        "ts": float(time.time()),
        "kind": str(event_type or "event"),
        "level": str(level or "info"),
        "payload": payload,
        "meta": dict(meta or {}),
    }
    line = json.dumps(rec, ensure_ascii=False)
    with _LOCK:
        with open(_bus_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return rec


def append(kind: str, payload: Any, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rec = emit(kind, payload, level="info", meta=meta)
    return {"ok": True, "event": rec}


def tail(n: int = 100) -> List[Dict[str, Any]]:
    n = max(1, min(int(n or 100), 5000))
    path = _bus_path()
    if not os.path.isfile(path):
        return []
    with _LOCK:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-n:]
    out: List[Dict[str, Any]] = []
    for line in lines:
        try:
            rec = json.loads(line)
            if isinstance(rec, dict):
                out.append(rec)
        except Exception:
            continue
    return out


def feed(
    since_ts: Optional[float] = None,
    limit: int = 200,
    kinds: Optional[Iterable[str] | str] = None,
    since: Optional[float] = None,
    kind: Optional[str] = None,
) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 200), 5000))
    since_cut = float(since if since is not None else (since_ts or 0.0))
    filter_kinds = _normalize_kinds(kinds, kind=kind)
    items = tail(max(limit * 4, limit))
    out: List[Dict[str, Any]] = []
    for rec in items:
        ts = float(rec.get("ts") or 0.0)
        if ts < since_cut:
            continue
        k = str(rec.get("kind") or "")
        if filter_kinds and k not in filter_kinds:
            continue
        out.append(rec)
    return out[-limit:]


def last_ts() -> float:
    items = tail(1)
    if not items:
        return 0.0
    return float(items[-1].get("ts") or 0.0)
