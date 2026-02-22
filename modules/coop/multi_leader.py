# -*- coding: utf-8 -*-
"""
modules/coop/multi_leader.py — «multi-lider»: ochered/peredacha roli veduschego.

Model:
- room -> { leader:str, queue:[str], members:set }
API:
- create(room, leader) -> ok
- add(room, user)      -> ok
- baton(room, to)      -> peredat «zhezl» konkretnomu polzovatelyu (esli chlen komnaty)
- rotate(room)         -> tsiklicheskaya rotatsiya po queue
- status(room)         -> sostoyanie komnaty

Integratsii:
- coop/game_sync, sync_keyboard, webrtc/dc mogut chitat tekuschego lidera dlya markirovki UI.

MOSTY:
- Yavnyy: (Orkestratsiya ↔ Igra) upravlenie pravom vesti sessiyu.
- Skrytyy #1: (Infoteoriya ↔ Spravedlivost) prozrachnaya ochered.
- Skrytyy #2: (Kibernetika ↔ Kontrol) peredacha roli — yavnyy akt, fiksiruetsya v sostoyanii.

ZEMNOY ABZATs:
V pamyati protsessa; chistye JSON ruchki. Net fonovykh demonov.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Set
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Dict[str, Any]] = {}  # room -> state

def create(room: str, leader: str) -> Dict[str, Any]:
    r = _state.setdefault(room, {"leader": leader, "queue": [], "members": set()})  # type: ignore
    r["leader"] = leader
    r["members"].add(leader)
    return {"ok": True, **status(room)}

def add(room: str, user: str) -> Dict[str, Any]:
    r = _state.setdefault(room, {"leader": user, "queue": [], "members": set()})  # type: ignore
    r["members"].add(user)
    if user not in r["queue"] and user != r["leader"]:
        r["queue"].append(user)
    return {"ok": True, **status(room)}

def baton(room: str, to: str) -> Dict[str, Any]:
    r = _state.get(room)
    if not r or to not in r["members"]:
        return {"ok": False, "error": "no_room_or_member"}
    if r["leader"] != to:
        # tekuschego lidera perenosim v konets ocheredi (esli on ne pust)
        old = r["leader"]
        if old and old not in r["queue"]:
            r["queue"].append(old)
        # «to» udalyaem iz ocheredi, delaem liderom
        r["queue"] = [x for x in r["queue"] if x != to]
        r["leader"] = to
    return {"ok": True, **status(room)}

def rotate(room: str) -> Dict[str, Any]:
    r = _state.get(room)
    if not r or not r["queue"]:
        return {"ok": False, "error": "empty_queue_or_room"}
    nxt = r["queue"].pop(0)
    return baton(room, nxt)

def status(room: str) -> Dict[str, Any]:
    r = _state.get(room) or {"leader":"", "queue": [], "members": set()}
    return {"ok": True, "leader": r["leader"], "queue": list(r["queue"]), "members": sorted(list(r["members"]))}