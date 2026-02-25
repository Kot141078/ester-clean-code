# -*- coding: utf-8 -*-
"""modules.thinking.missions - reestr “uchebnykh missiy” i progress.

Mosty:
- Yavnyy: REST-routy /missions/* ↔ etot modul (list_all/get/set_done/get_progress).
- Skrytyy #1: (UI ↔ Navigatsiya) — summary pozvolyaet risovat progress-beydzhi bez dopolnitelnoy logiciki.
- Skrytyy #2: (Memory ↔ Planirovschik) — enabled mozhno ispolzovat kak flag dlya avtozapuska missiy.

Zemnoy abzats:
Eto nebolshoy “reestr zadaniy”: spisok missiy s flazhkami done/enabled i funktsiyami dlya UI.
Khranenie - v pamyati protsessa (bez I/O), poetomu bezopasno dlya “zakrytoy korobki”.
# c=a+b"""
from __future__ import annotations
from typing import List, Dict, Optional, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Basic set of missions (can be expanded at runtime)
_M: List[Dict[str, Any]] = [
    {"id": "daily-digest", "title": "Daily Digest",     "enabled": False, "done": False},
    {"id": "sync-index",   "title": "Sinkhronizatsiya indeksa",   "enabled": False, "done": False},
]

def list_all() -> List[Dict]:
    """Polnyy spisok missiy (kopii elementov)."""
    return [dict(m) for m in _M]

def get(mid: str) -> Optional[Dict]:
    """Find mission by ID (copy)."""
    for m in _M:
        if m["id"] == mid:
            return dict(m)
    return None

def set_done(mid: str, done: bool = True) -> Dict:
    """Otmetit missiyu vypolnennoy/ne vypolnennoy."""
    for m in _M:
        if m["id"] == mid:
            m["done"] = bool(done)
            return {"ok": True, "id": mid, "done": m["done"]}
    return {"ok": False, "error": "not_found", "id": mid}

def get_progress() -> Dict[str, Any]:
    """Router-compatible progress summary:
      {
        "done": ZZF0Z,
        "enabled": ZZF1ZZ,
        "summary": ZZF2ZZ
      }"""
    done_map    = {m["id"]: bool(m.get("done"))    for m in _M}
    enabled_map = {m["id"]: bool(m.get("enabled")) for m in _M}
    total   = len(_M)
    done_ct = sum(1 for m in _M if m.get("done"))
    en_ct   = sum(1 for m in _M if m.get("enabled"))
    return {
        "done": done_map,
        "enabled": enabled_map,
        "summary": {"total": total, "done": done_ct, "enabled": en_ct},
    }