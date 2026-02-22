# -*- coding: utf-8 -*-
"""
modules/thinking/mentor_ab.py — A/B-slot «Nastavnika» s avto-otkatom.

Naznachenie:
- Derzhim dva nezavisimykh «rezhima» podsvetki/logiki: A (stabilnyy, po umolchaniyu) i B (eksperiment).
- Pereklyuchenie — REST. Avto-otkat — po taymeru (esli vklyuchen), chtoby minimizirovat risk «zalipnut» v B.

ENV:
- MENTOR_SLOT (A|B) — nachalnyy slot (default A)
- MENTOR_AUTO_ROLLBACK_SEC — 0 (off) ili >0 (sekundy do avto-vozvrata v A), po umolchaniyu 0

API (cherez routes/mentor_ab_routes.py):
- GET /mentor/ab/status           -> {slot, auto_sec, until_ts?}
- POST /mentor/ab/switch {"slot":"A"|"B"}
- POST /mentor/ab/auto  {"sec":60}     # vkl/pereustanovka avto-otkata
- POST /mentor/ab/cancel_auto          # vykl avto-otkata

MOSTY:
- Yavnyy: (Inzheneriya ↔ Ekspluatatsiya) bezopasnoe razvertyvanie s bystrym otkatom.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) dva fiksirovannykh kanala umenshayut veroyatnost regressiy.
- Skrytyy #2: (Kibernetika ↔ Kontrol) «refleks» vozvrata k A.

ZEMNOY ABZATs:
Rabotaet oflayn v odnom protsesse; sostoyaniya — v pamyati + ENV-defolty. Bez storonnikh servisov.

# c=a+b
"""
from __future__ import annotations
import os, time, threading
from typing import Optional, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_lock = threading.RLock()
_slot = os.environ.get("MENTOR_SLOT", "A").upper() if os.environ.get("MENTOR_SLOT") else "A"
_auto_sec = int(os.environ.get("MENTOR_AUTO_ROLLBACK_SEC", "0") or "0")
_until_ts: Optional[int] = None
_timer: Optional[threading.Timer] = None

def _apply_timer():
    global _timer, _until_ts
    with _lock:
        if _timer:
            _timer.cancel()
            _timer = None
            _until_ts = None
        if _auto_sec and _slot == "B":
            _until_ts = int(time.time()) + _auto_sec
            _timer = threading.Timer(_auto_sec, _rollback)
            _timer.daemon = True
            _timer.start()

def _rollback():
    global _slot, _timer, _until_ts
    with _lock:
        _slot = "A"
        if _timer:
            _timer.cancel()
        _timer = None
        _until_ts = None

def status() -> Dict[str, Any]:
    with _lock:
        return {"slot": _slot, "auto_sec": _auto_sec, "until_ts": _until_ts}

def switch(slot: str) -> Dict[str, Any]:
    global _slot
    slot = (slot or "A").upper()
    if slot not in ("A","B"):
        return {"ok": False, "error": "bad_slot"}
    with _lock:
        _slot = slot
        _apply_timer()
        return {"ok": True, "slot": _slot, "auto_sec": _auto_sec, "until_ts": _until_ts}

def set_auto(sec: int) -> Dict[str, Any]:
    global _auto_sec
    with _lock:
        _auto_sec = max(0, int(sec))
        _apply_timer()
        return {"ok": True, "slot": _slot, "auto_sec": _auto_sec, "until_ts": _until_ts}

def cancel_auto() -> Dict[str, Any]:
    return set_auto(0)