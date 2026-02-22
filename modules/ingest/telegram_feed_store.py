# -*- coding: utf-8 -*-
"""
Telegram feed JSONL store with lightweight in-memory index.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from modules.ingest.common import persist_dir


_LOCK = threading.RLock()
_LOADED = False
_BY_KEY: Dict[Tuple[str, str], Dict[str, Any]] = {}
_ORDER: List[Dict[str, Any]] = []


def _store_path() -> str:
    root = os.path.join(persist_dir(), "ingest")
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, "telegram_feed.jsonl")


def _record_key(rec: Dict[str, Any]) -> Tuple[str, str]:
    chat_id = str(rec.get("chat_id") or "")
    msg_id = str(rec.get("message_id") or "")
    return chat_id, msg_id


def _load_once() -> None:
    global _LOADED
    if _LOADED:
        return
    path = _store_path()
    if not os.path.isfile(path):
        _LOADED = True
        return
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue
            key = _record_key(rec)
            if not key[0]:
                continue
            _BY_KEY[key] = rec
            _ORDER.append(rec)
    _LOADED = True


def add_message(
    chat_id: Any,
    message_id: Any,
    text: str,
    ts: Optional[float] = None,
    chat_title: Optional[str] = None,
    kind: str = "message",
    **extra: Any,
) -> Dict[str, Any]:
    rec = {
        "chat_id": str(chat_id or ""),
        "message_id": str(message_id or ""),
        "chat_title": str(chat_title or chat_id or ""),
        "text": str(text or ""),
        "kind": str(kind or "message"),
        "ts": float(ts if ts is not None else time.time()),
    }
    if extra:
        rec.update(extra)
    if not rec["chat_id"]:
        return {"ok": False, "error": "chat_id_required"}
    if not rec["message_id"]:
        rec["message_id"] = str(int(rec["ts"] * 1000))

    key = _record_key(rec)
    with _LOCK:
        _load_once()
        if key in _BY_KEY:
            return {"ok": True, "duplicate": True, "event": _BY_KEY[key]}
        _BY_KEY[key] = rec
        _ORDER.append(rec)
        with open(_store_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True, "duplicate": False, "event": rec}


def latest(limit: int = 2000, chat_id: Optional[str] = None) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 2000), 10000))
    cid = str(chat_id or "").strip()
    with _LOCK:
        _load_once()
        rows = _ORDER if not cid else [r for r in _ORDER if str(r.get("chat_id") or "") == cid]
        rows = sorted(rows, key=lambda r: float(r.get("ts") or 0.0), reverse=True)
        return rows[:limit]


def list_events(
    chat_id: Optional[str] = None,
    limit: int = 200,
    since: float = 0.0,
    kind: Optional[str] = None,
    **_: Any,
) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 200), 5000))
    cid = str(chat_id or "").strip()
    since = float(since or 0.0)
    kind = str(kind).strip() if kind else ""
    with _LOCK:
        _load_once()
        out: List[Dict[str, Any]] = []
        for rec in _ORDER:
            if cid and str(rec.get("chat_id") or "") != cid:
                continue
            if kind and str(rec.get("kind") or "") != kind:
                continue
            if float(rec.get("ts") or 0.0) < since:
                continue
            out.append(rec)
        out.sort(key=lambda r: float(r.get("ts") or 0.0))
        return out[-limit:]
