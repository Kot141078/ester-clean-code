# -*- coding: utf-8 -*-
"""
modules/security/consent_gate.py — «shlyuz soglasiya» dlya sessiy polnogo kontrolya.

Model:
- Sessiya: {scope:str, ttl_sec:int, granted_at:epoch}
- Podderzhivaemye scope: "full_control" (kliki/klaviatura/goryachie deystviya), "read_only" i dr. mozhno dobavit.

API:
- grant(scope, ttl_sec) -> ok, until
- check(scope)          -> {allowed:bool, remaining_sec:int}
- revoke(scope)         -> ok
- status()              -> vse aktivnye

MOSTY:
- Yavnyy: (Etika ↔ Kontrol) deystviya silnogo effekta razreshayutsya polzovatelem.
- Skrytyy #1: (Infoteoriya ↔ Prozrachnost) prostoy status i TTL.
- Skrytyy #2: (Inzheneriya ↔ Sovmestimost) integriruetsya vyzovom /consent/check iz moduley deystviy.

ZEMNOY ABZATs:
Vse v pamyati protsessa; mozhno dopolnit zapisyu v fayl pri neobkhodimosti.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"sessions": {}}

def grant(scope: str, ttl_sec: int) -> Dict[str, Any]:
    scope = str(scope or "full_control")
    ttl = max(60, int(ttl_sec))
    now = int(time.time())
    _state["sessions"][scope] = {"granted_at": now, "ttl_sec": ttl}
    return {"ok": True, "scope": scope, "until": now+ttl}

def check(scope: str) -> Dict[str, Any]:
    scope = str(scope or "full_control")
    s = _state["sessions"].get(scope)
    if not s:
        return {"ok": True, "allowed": False, "remaining_sec": 0}
    now = int(time.time())
    rem = s["granted_at"] + s["ttl_sec"] - now
    if rem <= 0:
        del _state["sessions"][scope]
        return {"ok": True, "allowed": False, "remaining_sec": 0}
    return {"ok": True, "allowed": True, "remaining_sec": rem}

def revoke(scope: str) -> Dict[str, Any]:
    scope = str(scope or "full_control")
    _state["sessions"].pop(scope, None)
    return {"ok": True}

def status() -> Dict[str, Any]:
    out = {}
    now = int(time.time())
    for k, s in list(_state["sessions"].items()):
        rem = s["granted_at"] + s["ttl_sec"] - now
        if rem <= 0:
            del _state["sessions"][k]
        else:
            out[k] = {"remaining_sec": rem}
    return {"ok": True, "sessions": out}