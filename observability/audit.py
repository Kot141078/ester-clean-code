# -*- coding: utf-8 -*-
"""
observability/audit.py — universalnyy JSONL-audit.
Fayl: PERSIST_DIR/audit/requests.jsonl
API:
  write(entry: dict)
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_LOCK = threading.Lock()


def _persist_dir() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(base, exist_ok=True)
    return base


def _audit_path() -> str:
    p = os.path.join(_persist_dir(), "audit")
    os.makedirs(p, exist_ok=True)
    return os.path.join(p, "requests.jsonl")


def write(entry: Dict[str, Any]) -> None:
    row = dict(entry or {})
    row.setdefault("ts", time.time())
    try:
        with _LOCK:
            with open(_audit_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
