# -*- coding: utf-8 -*-
"""
modules/will/consent_gate.py — edinyy shlyuz soglasiya dlya silnykh deystviy.

API:
- check(need:list[str]|None=None, min_level:int=1) -> {allowed:bool, reason:str, snapshot:{}}
Pravila:
- paused == True → zapret
- level < min_level → zapret
- ttl_sec <= 0 → zapret (dlya silnykh deystviy)
- need ⊆ scope==True → inache zapret

MOSTY:
- Yavnyy: (Bezopasnost ↔ Ispolnitel) odna tochka resheniya.
- Skrytyy #1: (Kibernetika ↔ Stabilnost) TTL zaschischaet ot «vechnogo» razresheniya.
- Skrytyy #2: (Inzheneriya ↔ Sovmestimost) chistaya, bez zavisimostey.

ZEMNOY ABZATs:
Vstraivaetsya v lyuboy modul: pered deystviem vyzovi check(...).

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
from modules.autonomy.state import get as _get_state
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def check(need: List[str] | None = None, min_level: int = 1) -> Dict[str, Any]:
    st = _get_state()
    if st.get("paused"):
        return {"allowed": False, "reason": "paused", "snapshot": st}
    if int(st.get("level", 0)) < int(min_level):
        return {"allowed": False, "reason": "level_too_low", "snapshot": st}
    if st.get("ttl_sec", 0) <= 0 and (need or []):
        # esli deystvie «silnoe» (est potrebnosti), TTL obyazatelen
        return {"allowed": False, "reason": "ttl_expired", "snapshot": st}
    scope = st.get("scope") or {}
    for cap in (need or []):
        if not bool(scope.get(cap, False)):
            return {"allowed": False, "reason": f"scope_missing:{cap}", "snapshot": st}
    return {"allowed": True, "reason": "ok", "snapshot": st}