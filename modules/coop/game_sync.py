# -*- coding: utf-8 -*-
"""
modules/coop/game_sync.py — «sovmestnaya igra»: kadry, kvoty, latentnost.

Funktsii:
- configure(tick_rate, peers, quota_per_sec) — start parametrov
- tick() — uvelichivaet schetchik, shlet heartbeat v peers (cherez /webrtc/dc/send, esli zadan room)
- ingest_action(peer_id, action) — uchityvaet kvoty (per-peer actions/sec)
- status() — tekuschie metriki

Action format (primer):
{"kind":"input","type":"hotkey","seq":"CTRL+S"} | {"kind":"cursor","x":100,"y":200}

MOSTY:
- Yavnyy: (Orkestratsiya ↔ Igra) edinyy «takt» s limitami.
- Skrytyy #1: (Infoteoriya ↔ Spravedlivost) kvoty vyravnivayut nagruzku.
- Skrytyy #2: (Kibernetika ↔ Bezopasnost) mozhno podklyuchit consent_gate na storone potrebiteley deystviy.

ZEMNOY ABZATs:
Bez vneshnikh soketov: metriki v pamyati, rassylka cherez psevdo-DC ili REST.

# c=a+b
"""
from __future__ import annotations
import time, json, threading
from typing import Dict, Any, List, Optional
import http.client
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {
    "running": False, "tick_rate": 20, "tick": 0,
    "peers": [], "quota": 5, "room": None,
    "hist": {},  # peer_id -> [timestamps]
}
_thr: Optional[threading.Thread] = None

def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store  # type: ignore
            memory_add("dialog", text, meta=meta)
        except Exception:
            pass
        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if False:
                pass
        except Exception:
            pass
    except Exception:
        pass

def _now() -> float: return time.time()

def configure(tick_rate: int, peers: List[str], quota_per_sec: int, room: str|None = None) -> Dict[str, Any]:
    _state.update({"tick_rate": max(5,int(tick_rate)), "peers": list(peers or []), "quota": max(1,int(quota_per_sec)), "room": room})
    return {"ok": True, **status()}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=8.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t=r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False}

def _send_room(data: Dict[str, Any]) -> None:
    room = _state.get("room")
    if not room: return
    _post("/webrtc/dc/send", {"room": room, "client": "leader", "data": data, "broadcast": True})

def start() -> Dict[str, Any]:
    if _state.get("running"): return {"ok": True, **status()}
    _state["running"] = True
    def loop():
        dt = 1.0/float(_state["tick_rate"])
        while _state.get("running"):
            _state["tick"] += 1
            _send_room({"type":"tick","tick":_state["tick"]})
            time.sleep(dt)
    global _thr
    _thr = threading.Thread(target=loop, daemon=True); _thr.start()
    try:
        _mirror_background_event(
            "[GAME_SYNC_START]",
            "game_sync",
            "start",
        )
    except Exception:
        pass
    return {"ok": True, **status()}

def stop() -> Dict[str, Any]:
    _state["running"] = False
    try:
        _mirror_background_event(
            "[GAME_SYNC_STOP]",
            "game_sync",
            "stop",
        )
    except Exception:
        pass
    return {"ok": True, **status()}

def _allow(peer_id: str) -> bool:
    q = int(_state.get("quota",5))
    arr = _state["hist"].setdefault(peer_id, [])
    now = _now()
    arr[:] = [t for t in arr if now - t <= 1.0]
    if len(arr) >= q:
        return False
    arr.append(now); return True

def ingest_action(peer_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
    if not _allow(peer_id):
        try:
            _mirror_background_event(
                f"[GAME_SYNC_QUOTA] peer={peer_id}",
                "game_sync",
                "quota_exceeded",
            )
        except Exception:
            pass
        return {"ok": False, "reason": "quota_exceeded"}
    # transliruem v komnatu srazu, chtoby drugie klienty uvideli
    _send_room({"type":"action","from": peer_id, "payload": action})
    return {"ok": True}

def status() -> Dict[str, Any]:
    return {"ok": True, "running": bool(_state.get("running")), "tick_rate": int(_state.get("tick_rate",20)), "tick": int(_state.get("tick",0)), "peers": list(_state.get("peers",[])), "quota": int(_state.get("quota",5)), "room": _state.get("room")}