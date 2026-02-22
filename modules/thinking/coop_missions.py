# -*- coding: utf-8 -*-
"""
modules/thinking/coop_missions.py — kooperativnye missii veduschiy↔vedomyy.

Naznachenie:
- Derzhim komnatu kooperativa: host(leader), peers(list), tekuschaya missiya, indeks shaga.
- Komandy: bind(peer), start(mission_id), next(), status()

Transport:
- Lokalnaya set cherez uzhe realizovannyy /peer/proxy (HTTP).

MOSTY:
- Yavnyy: (Volya ↔ Sinkhronizatsiya) odin plan shagaetsya sinkhronno na dvukh mashinakh.
- Skrytyy #1: (Kibernetika ↔ Bezopasnost) yavnoe soglasie na domen "rpa.coop" uzhe vnedreno ranee.
- Skrytyy #2: (Inzheneriya ↔ Memory) prostaya struktura komnaty — stabilnyy kontekst dlya sovmestnoy sessii.

ZEMNOY ABZATs:
Bez novykh demonov/servisov: odin fayl sostoyaniya v pamyati, HTTP-proxy vyzovy; missii berem iz uzhe suschestvuyuschikh marshrutov.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_ROOM: Dict[str, Any] = {"peers": [], "mission": None, "index": 0}

def bind(peer: str) -> Dict[str, Any]:
    peer = (peer or "").strip()
    if not peer: return {"ok": False, "error": "peer_required"}
    if peer not in _ROOM["peers"]:
        _ROOM["peers"].append(peer)
    return {"ok": True, "peers": list(_ROOM["peers"])}

def start(mission_id: str) -> Dict[str, Any]:
    _ROOM["mission"] = mission_id
    _ROOM["index"] = 0
    return {"ok": True, "mission": mission_id, "index": 0}

def next_step() -> Dict[str, Any]:
    if not _ROOM["mission"]:
        return {"ok": False, "error": "no_mission"}
    i = _ROOM["index"]
    _ROOM["index"] = i + 1
    return {"ok": True, "index": _ROOM["index"]}

def status() -> Dict[str, Any]:
    return {"ok": True, "peers": list(_ROOM["peers"]), "mission": _ROOM["mission"], "index": _ROOM["index"]}