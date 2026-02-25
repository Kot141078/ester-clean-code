# -*- coding: utf-8 -*-
"""modules/security/rate_limiter.py - ogranichitel frequency sobytiy (per key).

Fayly: data/security/rate_limiter.json
Strategy: skolzyaschee okno 60s, limit sobytiy na klyuch (for example, "hotkey" or "workflow:name").

API:
- set_limit(key:str, limit_per_min:int)
- should_allow(key:str) -> {allow:bool, reason?}
- status() -> tekuschie limity/schetchiki (ukrupnenno)

MOSTY:
- Yavnyy: (Bezopasnost ↔ Kontrol) zaschita ot burstov.
- Skrytyy #1: (Infoteoriya ↔ Determinizm) prostaya, obyasnimaya logika.
- Skrytyy #2: (Memory ↔ Ekspluatatsiya) fayl s limitami dlya povtornogo starta.

ZEMNOY ABZATs:
Odin JSON-fayl s limitami, pamyat protsessa - taymstampy poslednikh sobytiy.

# c=a+b"""
from __future__ import annotations
import os, json, time
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR  = os.path.join(ROOT, "data", "security")
os.makedirs(DIR, exist_ok=True)
FILE = os.path.join(DIR, "rate_limiter.json")

_limits: Dict[str, int] = {}
_hist: Dict[str, List[float]] = {}

def _load():
    global _limits
    if os.path.exists(FILE):
        try:
            with open(FILE,"r",encoding="utf-8") as f:
                _limits = json.load(f).get("limits", {})
        except Exception:
            _limits = {}

def _save():
    with open(FILE,"w",encoding="utf-8") as f:
        json.dump({"limits": _limits}, f, ensure_ascii=False, indent=2)

_load()

def set_limit(key: str, limit_per_min: int) -> Dict[str, Any]:
    _limits[str(key)] = int(max(1, limit_per_min))
    _save()
    return {"ok": True, "limits": _limits}

def should_allow(key: str) -> Dict[str, Any]:
    key = str(key)
    limit = int(_limits.get(key, 0))
    if limit <= 0:
        return {"ok": True, "allow": True}
    now = time.time()
    hist = _hist.get(key, [])
    # ochistit > 60s
    hist = [t for t in hist if now - t <= 60.0]
    allowed = len(hist) < limit
    if allowed:
        hist.append(now); _hist[key] = hist
        return {"ok": True, "allow": True}
    return {"ok": True, "allow": False, "reason": "rate_limited", "used": len(hist), "limit": limit}

def status() -> Dict[str, Any]:
    return {"ok": True, "limits": dict(_limits), "active_keys": list(_hist.keys())}