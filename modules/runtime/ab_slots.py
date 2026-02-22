# -*- coding: utf-8 -*-
"""
modules/runtime/ab_slots.py — A/B-sloty komponentov s TTL i avto-otkatom (sovmestimostnyy fasad).

Mosty:
- Yavnyy: (Sloty komponentov ↔ Edinoe yadro) API sokhranen, realizatsiya unifitsirovana cherez ab_unified.
- Skrytyy #1: (Healthz ↔ Bezopasnost) dlya prostykh proverok ostavlen HEALTH_URL_SINGLE v yadre.
- Skrytyy #2: (Planirovschik ↔ Avtomatika) sweep_expired mozhno vyzyvat iz kron/planirovschika.

Zemnoy abzats:
Fasad ostavlyaet prezhnie funktsii i peremennye, no pod kapotom odin dvizhok — menshe raskhozhdeniy i bagov.
# c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Dict

from .ab_unified import (
    COMP_DB as _DB,
    COMP_DEFAULT_TTL_SEC as _TTL,
    HEALTH_URL_SINGLE as _HEALTH,
    comp_status as _status,
    comp_switch as _switch,
    comp_commit as _commit,
    comp_rollback as _rollback,
    comp_sweep_expired as _sweep,
)

# Sokhranenie starykh «globalov» dlya obratnoy sovmestimosti
DB = os.getenv("RUNTIME_AB_DB", _DB)
TTL = int(os.getenv("RUNTIME_AB_DEFAULT_TTL_SEC", str(_TTL)) or str(_TTL))
HEALTH = os.getenv("RUNTIME_HEALTH_URL", _HEALTH)

def status() -> Dict[str, Any]:
    return _status()

def switch(component: str, slot: str, ttl_sec: int | None = None) -> Dict[str, Any]:
    return _switch(component, slot, ttl_sec)

def commit(component: str) -> Dict[str, Any]:
    return _commit(component)

def rollback(component: str) -> Dict[str, Any]:
    return _rollback(component)

def sweep_expired() -> Dict[str, Any]:
    return _sweep()
