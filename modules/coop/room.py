# -*- coding: utf-8 -*-
"""
modules/coop/room.py — legkiy kooperativnyy sloy (komnaty, lider, kvoty, sobytiya).

Funktsional:
- komnaty: join/leave, spisok pirov, status
- lider: set/rotate
- kvoty: tick_hz (logicheskie tiki), actions_per_sec (APS)
- sobytiya: append/broadcast, pull (posledovatelnost seq i polling)
- bezopasnyy forvard silnykh sobytiy (hotkey/text) — proverka consent_gate na LIDERE

Ogranicheniya:
- In-memory, bez fonovykh potokov i demonov
- Polling po GET /coop/pull?room=...&since=seq (dlinnyy optsionalno, no tut obychnyy korotkiy)

MOSTY:
- Yavnyy: (Sovmestnost ↔ Kontrol) zhezl lidera opredelyaet, kto realno «zhmet».
- Skrytyy #1: (Infoteoriya ↔ Predskazuemost) tick/APS zadayut ritm i limitiruyut potok deystviy.
- Skrytyy #2: (Inzheneriya ↔ Sovmestimost) chistyy JSON i lokalnye REST-vyzovy bez vneshnikh brokerov.

ZEMNOY ABZATs:
Eto shina sobytiy v pamyati protsessa. Lider — edinstvennyy, kto ispolnyaet «silnye» deystviya. Ostalnye poluchayut sobytiya v log (dlya UI/sinkhronizatsii).

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import time, threading, json, http.client

from modules.will.consent_gate import check as will_check
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_LOCK = threading.Lock()

_rooms: Dict[str, Dict[str, Any]] = {}  # room -> {peers:{peer_id:{name,last_seen}}, leader:str|None, tick:int, tick_hz:int, aps:int, seq:int, events:list}
DEFAULTS = {"tick_hz": 20, "aps": 5}

def _room(r: str) -> Dict[str, Any]:
    with _LOCK:
        rm = _rooms.get(r)
        if not rm:
            rm = {"peers": {}, "leader": None, "tick": 0, "tick_hz": DEFAULTS["tick_hz"], "aps": DEFAULTS["aps"], "seq": 0, "events": []}
            _rooms[r] = rm
        return rm

def join(room: str, peer_id: str, name: str) -> Dict[str, Any]:
    now = int(time.time())
    with _LOCK:
        rm = _room(room)
        rm["peers"][peer_id] = {"name": name or peer_id, "last_seen": now}
        if not rm["leader"]:
            rm["leader"] = peer_id
        return status(room)

def leave(room: str, peer_id: str) -> Dict[str, Any]:
    with _LOCK:
        rm = _room(room)
        rm["peers"].pop(peer_id, None)
        if rm["leader"] == peer_id:
            rm["leader"] = next(iter(rm["peers"].keys()), None)
        return status(room)

def set_leader(room: str, peer_id: str) -> Dict[str, Any]:
    with _LOCK:
        rm = _room(room)
        if peer_id in rm["peers"]:
            rm["leader"] = peer_id
        return status(room)

def rotate_leader(room: str) -> Dict[str, Any]:
    with _LOCK:
        rm = _room(room)
        peers = list(rm["peers"].keys())
        if rm["leader"] in peers and peers:
            i = peers.index(rm["leader"])
            rm["leader"] = peers[(i+1) % len(peers)]
        elif peers:
            rm["leader"] = peers[0]
        return status(room)

def set_quota(room: str, tick_hz: int | None = None, aps: int | None = None) -> Dict[str, Any]:
    with _LOCK:
        rm = _room(room)
        if tick_hz is not None: rm["tick_hz"] = max(1, int(tick_hz))
        if aps is not None: rm["aps"] = max(1, int(aps))
        return status(room)

def _append_event(rm: Dict[str, Any], ev: Dict[str, Any]) -> int:
    rm["seq"] += 1
    ev["seq"] = rm["seq"]
    ev["ts"] = time.time()
    rm["events"].append(ev)
    # ogranichim khvost
    if len(rm["events"]) > 2000:
        rm["events"] = rm["events"][-1000:]
    return ev["seq"]

def broadcast(room: str, peer_id: str, ev_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Esli peer_id == leader i sobytie «silnoe» (hotkey/text), probuem ispolnit lokalno (consent_gate).
    Vsegda pishem v shinu sobytiy; klienty zaberut cherez /pull.
    """
    rm = _room(room)
    leader = rm.get("leader")
    executed = None
    detail = None

    if peer_id == leader and ev_type in ("hotkey","text"):
        chk = will_check(["rpa_ui"], min_level=2)
        if chk.get("allowed"):
            # lokalnyy forvard
            detail = _forward(ev_type, payload)
            executed = bool(detail.get("ok", True))
        else:
            executed = False
            detail = {"ok": False, "reason": "consent_denied"}

    with _LOCK:
        seq = _append_event(rm, {"room": room, "from": peer_id, "type": ev_type, "payload": payload, "executed": executed, "detail": detail})

    return {"ok": True, "seq": seq, "executed": executed, "leader": leader}

def tick(room: str, n: int = 1) -> Dict[str, Any]:
    with _LOCK:
        rm = _room(room)
        rm["tick"] += max(1, int(n))
        seq = _append_event(rm, {"room": room, "from": "system", "type": "tick", "payload": {"tick": rm["tick"]}})
        return {"ok": True, "tick": rm["tick"], "seq": seq}

def pull(room: str, since: int = 0, limit: int = 200) -> Dict[str, Any]:
    rm = _room(room)
    with _LOCK:
        items = [e for e in rm["events"] if e.get("seq", 0) > int(since)]
        items = items[:max(1, min(500, int(limit)))]
        return {"ok": True, "events": items, "next_seq": items[-1]["seq"] if items else since}

def status(room: str) -> Dict[str, Any]:
    with _LOCK:
        rm = _room(room)
        return {
            "ok": True,
            "room": room,
            "leader": rm["leader"],
            "tick": rm["tick"],
            "tick_hz": rm["tick_hz"],
            "aps": rm["aps"],
            "peers": rm["peers"],
            "seq": rm["seq"],
            "events_tail": max(0, len(rm["events"]))
        }

# ---- local forward helpers ----
def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _forward(ev_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if ev_type == "hotkey":
        return _post("/sync_keyboard/send_hotkey", {"hotkey": str(payload.get("keys",""))})
    if ev_type == "text":
        return _post("/sync_keyboard/send_text", {"text": str(payload.get("text",""))})
    return {"ok": True}