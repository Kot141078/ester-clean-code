# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, Iterable, List, Optional
from pathlib import Path
import os, json, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _data_dir() -> Path:
    base = os.environ.get("ESTER_DATA_DIR") or os.environ.get("ESTER_DATA_ROOT") or "data"
    p = Path(base).expanduser()
    (p / "chat").mkdir(parents=True, exist_ok=True)
    return p

def file_for_sid(sid: str) -> Path:
    sid = (sid or "default").strip() or "default"
    p = _data_dir() / "chat" / f"{sid}.jsonl"
    return p

def append(sid: str, role: str, text: str, meta: Optional[Dict[str, Any]] = None) -> None:
    rec = {
        "ts": int(time.time()*1000),
        "sid": sid,
        "role": role,
        "text": text,
        "meta": meta or {},
    }
    with file_for_sid(sid).open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def load(sid: str, limit: int = 100) -> List[Dict[str, Any]]:
    p = file_for_sid(sid)
    out: List[Dict[str, Any]] = []
    if not p.exists():
        return out
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = f.readline() if False else line  # noop for clarity
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    if limit > 0:
        return out[-limit:]
    return out
