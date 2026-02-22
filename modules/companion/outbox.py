# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOCK = threading.RLock()


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _outbox_dir() -> Path:
    p = (_persist_dir() / "outbox").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def messages_path() -> Path:
    p = (_outbox_dir() / "messages.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def acks_path() -> Path:
    p = (_outbox_dir() / "acks.jsonl").resolve()
    if not p.exists():
        p.touch()
    return p


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(dict(row or {}), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def enqueue(
    kind: str,
    text: str,
    meta: Optional[Dict[str, Any]] = None,
    *,
    chain_id: str = "",
    related_action: str = "",
) -> Dict[str, Any]:
    msg_id = "msg_" + uuid.uuid4().hex[:12]
    row = {
        "id": msg_id,
        "ts": int(time.time()),
        "kind": str(kind or "note"),
        "text": str(text or "").strip(),
        "meta": dict(meta or {}),
        "chain_id": str(chain_id or ""),
        "related_action": str(related_action or ""),
        "ok": True,
    }
    with _LOCK:
        _append_jsonl(messages_path(), row)
    return {"ok": True, "msg_id": msg_id, "row": row, "messages_path": str(messages_path())}


def _tail_lines(path: Path, n: int) -> List[str]:
    lim = max(1, int(n or 1))
    if not path.exists() or path.stat().st_size <= 0:
        return []
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        data = b""
        found = 0
        chunk_size = 4096
        while pos > 0 and found <= lim:
            step = min(chunk_size, pos)
            pos -= step
            f.seek(pos, os.SEEK_SET)
            chunk = f.read(step)
            data = chunk + data
            found = data.count(b"\n")
    text = data.decode("utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-lim:]


def tail(n: int = 20) -> List[Dict[str, Any]]:
    with _LOCK:
        lines = _tail_lines(messages_path(), max(1, int(n or 20)))
    out: List[Dict[str, Any]] = []
    for line in lines:
        try:
            obj = json.loads(line)
        except Exception:
            obj = {"ok": False, "error": "invalid_jsonl", "raw": line}
        if isinstance(obj, dict):
            out.append(obj)
    return out


def mark_delivered(msg_id: str, channel: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    mid = str(msg_id or "").strip()
    ch = str(channel or "").strip()
    if not mid:
        return {"ok": False, "error": "msg_id_required"}
    if not ch:
        return {"ok": False, "error": "channel_required"}
    row = {
        "ack_id": "ack_" + uuid.uuid4().hex[:12],
        "ts": int(time.time()),
        "msg_id": mid,
        "channel": ch,
        "meta": dict(meta or {}),
        "ok": True,
    }
    with _LOCK:
        _append_jsonl(acks_path(), row)
    return {"ok": True, "ack": row, "acks_path": str(acks_path())}


def summary(recent_n: int = 50) -> Dict[str, Any]:
    rows = tail(max(1, int(recent_n or 50)))
    last = dict(rows[-1]) if rows else {}
    return {
        "ok": True,
        "count_recent": len(rows),
        "last_msg_ts": last.get("ts"),
        "last_kind": str(last.get("kind") or ""),
        "last_explained_chain_id": str(last.get("chain_id") or ""),
        "paths": {"messages": str(messages_path()), "acks": str(acks_path())},
    }


__all__ = ["messages_path", "acks_path", "enqueue", "tail", "mark_delivered", "summary"]

