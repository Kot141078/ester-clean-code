
# -*- coding: utf-8 -*-
"""
modules/webrtc/datachannel_stub.py — psevdo-WebRTC DataChannel na baze lokalnykh ocheredey
(HTTP POST + SSE). Bez STUN/TURN i vneshnikh zavisimostey. Podkhodit dlya LAN/odnoy mashiny.

Model:
- room_id -> { clients: {client_id: queue[list[str]]}, last_heartbeat }
- Klient podpisyvaetsya na SSE /webrtc/dc/recv?room&client i otpravlyaet POST /webrtc/dc/send
- Format dannykh — svobodnyy JSON-obekt (stroka), peredaem kak text/event-stream.

Integratsii:
- sync_keyboard, coop/game_sync, macro_recorder mogut ispolzovat etot kanal dlya bystroy rassylki sobytiy.

MOSTY:
- Yavnyy: (Svyaznost ↔ Nizkaya zaderzhka) obschiy shinoy-kanal sobytiy bez vneshnikh brokerov.
- Skrytyy #1: (Infoteoriya ↔ Prozrachnost) prostye ocheredi v pamyati, determinirovannyy SSE.
- Skrytyy #2: (Kibernetika ↔ Kontrol) vsya «sila» vse esche prokhodit cherez consent_gate v potreblyayuschikh modulyakh.

ZEMNOY ABZATs:
SSE long-poll bez tredov/demonov; ochistka visyachikh klientov po taym-autu heartbeat. Vse offlayn.

# c=a+b
"""
from __future__ import annotations
import time, json, threading
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_room: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()
TTL_SEC = 60

def _now() -> int: return int(time.time())

def open_room(room_id: str, client_id: str) -> Dict[str, Any]:
    with _lock:
        r = _room.setdefault(room_id, {"clients": {}, "ts": _now()})
        r["clients"].setdefault(client_id, {"q": [], "ts": _now()})
    return {"ok": True, "room": room_id, "client": client_id}

def heartbeat(room_id: str, client_id: str) -> Dict[str, Any]:
    with _lock:
        r = _room.get(room_id)
        if not r: return {"ok": False, "error": "no_room"}
        c = r["clients"].get(client_id)
        if not c: return {"ok": False, "error": "no_client"}
        c["ts"] = _now(); r["ts"] = _now()
    return {"ok": True}

def send(room_id: str, client_id: str, payload: Any, broadcast: bool = True, target: str|None = None) -> Dict[str, Any]:
    data = json.dumps({"from": client_id, "ts": _now(), "data": payload}, ensure_ascii=False)
    with _lock:
        r = _room.get(room_id)
        if not r: return {"ok": False, "error": "no_room"}
        targets = []
        if broadcast:
            targets = [k for k in r["clients"].keys() if k != client_id]
        elif target:
            if target in r["clients"]: targets = [target]
        for t in targets:
            r["clients"][t]["q"].append(data)
    return {"ok": True, "sent": True, "targets": len(targets)}

def drain(room_id: str, client_id: str) -> List[str]:
    with _lock:
        r = _room.get(room_id); 
        if not r or client_id not in r["clients"]: return []
        q = r["clients"][client_id]["q"]; r["clients"][client_id]["q"] = []
        return q

def gc() -> None:
    with _lock:
        now = _now()
        dead_rooms = []
        for rid, r in _room.items():
            dead_clients = []
            for cid, c in r["clients"].items():
                if now - c["ts"] > TTL_SEC:
                    dead_clients.append(cid)
            for cid in dead_clients:
                del r["clients"][cid]
            if not r["clients"] and now - r["ts"] > TTL_SEC:
                dead_rooms.append(rid)
        for rid in dead_rooms:
            del _room[rid]