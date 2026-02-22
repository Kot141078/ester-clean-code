# -*- coding: utf-8 -*-
"""
modules/autonomy/state.py — edinoe sostoyanie avtonomii Ester.

Soderzhit:
- level: 0..3 (0—passiv, 1—semi, 2—agent, 3—tsikl+planirovschik)
- scope: razresheniya deystviy (rpa_ui, network, files, dialog, game)
- ttl_sec: ostavsheesya vremya na silnye deystviya (decrement na chtenii)
- paused: globalnaya pauza voli
- since, updated: metki vremeni

MOSTY:
- Yavnyy: (Volya ↔ Deystvie) tsentralizovannyy istochnik istiny dlya vsekh silnykh moduley.
- Skrytyy #1: (Kibernetika ↔ Kontrol) TTL i pauza — regulyatory «tyagi».
- Skrytyy #2: (Infoteoriya ↔ Prozrachnost) neizmenyaemyy interfeys get()/set(), prostye tipy.

ZEMNOY ABZATs:
V pamyati protsessa, bez BD i demonov. Potokobezopasnost — cherez prostoy lock.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any
import time, threading
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_lock = threading.Lock()
_state: Dict[str, Any] = {
    "level": 0,
    "scope": {"rpa_ui": False, "network": False, "files": False, "dialog": True, "game": False},
    "ttl_sec": 0,
    "paused": False,
    "since": int(time.time()),
    "updated": int(time.time())
}

def _now() -> int: return int(time.time())

def get() -> Dict[str, Any]:
    with _lock:
        # lenivoe «sgoranie» TTL: umenshaem s momenta poslednego obrascheniya
        now = _now()
        elapsed = now - int(_state.get("updated", now))
        ttl = max(0, int(_state.get("ttl_sec", 0)) - elapsed)
        if ttl != _state.get("ttl_sec", 0):
            _state["ttl_sec"] = ttl
        _state["updated"] = now
        return {k: (_state[k].copy() if isinstance(_state[k], dict) else _state[k]) for k in _state}

def set_level(level: int) -> Dict[str, Any]:
    with _lock:
        _state["level"] = max(0, min(3, int(level)))
        _state["updated"] = _now()
        return get()

def set_scope(scope: Dict[str, Any], ttl: int | None = None) -> Dict[str, Any]:
    with _lock:
        for k, v in (scope or {}).items():
            if k in _state["scope"]:
                _state["scope"][k] = bool(v)
        if ttl is not None:
            _state["ttl_sec"] = max(0, int(ttl))
        _state["updated"] = _now()
        return get()

def pause(on: bool) -> Dict[str, Any]:
    with _lock:
        _state["paused"] = bool(on)
        _state["updated"] = _now()
        return get()

def revoke() -> Dict[str, Any]:
    with _lock:
        _state["ttl_sec"] = 0
        _state["scope"] = {k: False for k in _state["scope"].keys()}
        _state["updated"] = _now()
        return get()