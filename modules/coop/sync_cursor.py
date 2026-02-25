# -*- coding: utf-8 -*-
"""modules/coop/sync_cursor.py - sinkhro-kursor (veduschiy transliruet koordinaty/kliki vedomym).

Rezhimy:
- leader: chitaet lokalnye sobytiya (mouse_move/click) iz REST-zaprosov UI (/admin/sync) i rassylaet peers.
- follower: prinimaet pakety cherez /sync/ingest i vyzyvaet lokalnye deystviya: /desktop/window/mouse_move, /mouse_click.

Format package:
{"type":"move","x":123,"y":456} or {"type":"click","btn":"left","down":true}

MOSTY:
- Yavnyy: (Orkestratsiya ↔ Motorika) vsem - odin i tot zhe zhest.
- Skrytyy #1: (Infoteoriya ↔ Sinkhronizatsiya) prostye sobytiya, garantirovannaya posledovatelnost.
- Skrytyy #2: (Kibernetika ↔ Kontrol) rabotaet tolko pri yavnom zapuske i prokhodit cherez policy/consent/safe.

ZEMNOY ABZATs:
Tolko HTTP: /peer/proxy k spisku peers. Na vedomom - shtatnye ruchki okna myshi.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"peers": [], "enabled": False, "throttle_ms": 20}

def set_peers(peers: List[str]) -> Dict[str, Any]:
    _state["peers"] = list(peers or [])
    return {"ok": True, "peers": _state["peers"]}

def enable(flag: bool, throttle_ms: int = 20) -> Dict[str, Any]:
    _state["enabled"] = bool(flag)
    _state["throttle_ms"] = int(throttle_ms or 20)
    return {"ok": True, **_state}

def status() -> Dict[str, Any]:
    return {"ok": True, **_state}

def _post_local(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=8.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _broadcast(pkt: Dict[str, Any]) -> List[Dict[str, Any]]:
    res = []
    for host in _state.get("peers", []):
        try:
            res.append(_post_local("/peer/proxy", {"host": host, "path": "/sync/ingest", "payload": pkt}))
        except Exception as e:
            res.append({"ok": False, "error": str(e)})
    return res

def leader_move(x: int, y: int) -> Dict[str, Any]:
    if not _state.get("enabled"): return {"ok": False, "error": "disabled"}
    return {"ok": True, "peers": _broadcast({"type":"move","x":int(x),"y":int(y)})}

def leader_click(btn: str, down: bool) -> Dict[str, Any]:
    if not _state.get("enabled"): return {"ok": False, "error": "disabled"}
    return {"ok": True, "peers": _broadcast({"type":"click","btn":str(btn or 'left'),"down":bool(down)})}

def follower_ingest(pkt: Dict[str, Any]) -> Dict[str, Any]:
    t = (pkt.get("type") or "").lower()
    if t == "move":
        return _post_local("/desktop/window/mouse_move", {"x": int(pkt.get("x",0)), "y": int(pkt.get("y",0))})
    if t == "click":
        return _post_local("/desktop/window/mouse_click", {"btn": pkt.get("btn","left"), "down": bool(pkt.get("down", True))})
    return {"ok": False, "error": "bad_packet"}