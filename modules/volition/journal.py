# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

_LOCK = threading.RLock()


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def journal_path() -> Path:
    override = (os.getenv("ESTER_VOLITION_JOURNAL_PATH") or "").strip()
    if override:
        p = Path(override).resolve()
    else:
        p = (_persist_dir() / "volition" / "decisions.jsonl").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.touch()
    return p


def append(record: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(record or {})
    row.setdefault("ts", int(time.time()))
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    with _LOCK:
        with journal_path().open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    return row


def _tail_lines(path: Path, limit: int) -> List[str]:
    n = max(1, int(limit))
    if not path.exists() or path.stat().st_size <= 0:
        return []
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        block = 4096
        data = b""
        found = 0
        while pos > 0 and found <= n:
            step = min(block, pos)
            pos -= step
            f.seek(pos, os.SEEK_SET)
            chunk = f.read(step)
            data = chunk + data
            found = data.count(b"\n")
        text = data.decode("utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-n:]


def tail(limit: int = 20) -> List[Dict[str, Any]]:
    n = max(1, int(limit or 20))
    path = journal_path()
    with _LOCK:
        lines = _tail_lines(path, n)
    out: List[Dict[str, Any]] = []
    for line in lines:
        try:
            obj = json.loads(line)
        except Exception:
            obj = {"ok": False, "error": "invalid_jsonl", "raw": line}
        if isinstance(obj, dict):
            out.append(obj)
    return out


__all__ = ["journal_path", "append", "tail"]
