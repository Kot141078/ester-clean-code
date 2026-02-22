# -*- coding: utf-8 -*-
"""
modules.backup.backup_logic — logika importa/eksporta slepkov (rasshiren).

MOSTY:
- Yavnyy: import_state(), export_state().
- Skrytyy #1: (Validatsiya) determinirovannye otvety bez pobochnykh effektov.
- Skrytyy #2: (Sovmestimost) prostye slovari bez modeley.

ZEMNOY ABZATs:
Dvizhenie «tuda-obratno»: UI mozhet i vygruzhat, i zagruzhat sostoyaniya.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def import_state(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if payload is None: payload = {}
    if not isinstance(payload, dict): return {"ok": False, "error": "invalid_payload_type"}
    return {"ok": True, "imported_keys": list(payload.keys()), "size": len(payload)}

def export_state(state: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if state is None: state = {}
    if not isinstance(state, dict): return {"ok": False, "error": "invalid_state_type"}
    return {"ok": True, "state": dict(state), "size": len(state)}

# c=a+b