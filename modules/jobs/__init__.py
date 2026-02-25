
# -*- coding: utf-8 -*-
"""modules.jobs - prostoy in-memory planirovschik.
Mosty:
- Yavnyy: enqueue()/status().
- Skrytyy #1: (Planirovschik ↔ Podsoznanie) — mozhet vyzyvat subconscious.tick.
- Skrytyy #2: (DX ↔ Otkazoustoychivost) — bez vneshnikh brokerov.

Zemnoy abzats:
Nuzhna ochered pryamo seychas - berem pamyat protsessa.
# c=a+b"""
from __future__ import annotations
import time, os
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_MAX = int(os.getenv("ESTER_JOBS_MAX","1024"))
Q: List[Dict[str, Any]] = []

def enqueue(kind: str, payload: dict) -> dict:
    if len(Q) >= _MAX:
        return {"ok": False, "reason": "queue_full", "size": len(Q)}
    item = {"ts": int(time.time()), "kind": kind, "payload": payload}
    Q.append(item)
    return {"ok": True, "size": len(Q)}

def status() -> dict:
    return {"ok": True, "size": len(Q)}