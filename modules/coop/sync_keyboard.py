# -*- coding: utf-8 -*-
"""modules/coop/sync_keyboard.py — sinkhronizatsiya klaviatury leader→followers.

Format package:
{"type":"hotkey","seq":"CTRL+S"} | {"type":"text","value":"hello"}

Podderzhka:
- hotkey → /desktop/window/hotkey
- text → /desktop/window/type_text (esli otsutstvuet — otpravlyaem po simvolu cherez hotkey s modifikatorom? zdes ostavlyaem tolko hotkey)

MOSTY:
- Yavnyy: (Orkestratsiya ↔ Motorika) odin zhest - mnogo mashin.
- Skrytyy #1: (Infoteoriya ↔ Bezopasnost) integratsiya so “shlyuzom soglasiya.”
- Skrytyy #2: (Kibernetika ↔ Kontrol) yavnyy start/stop, spisok peers.

ZEMNOY ABZATs:
HTTP-prosloyka: lider ot UI shlet sobytiya → rassylaem /peer/proxy na vedomye.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json, os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"peers": [], "enabled": False}

def set_peers(peers: List[str]) -> Dict[str, Any]:
    _state["peers"] = list(peers or [])
    return {"ok": True, "peers": _state["peers"]}

def enable(flag: bool) -> Dict[str, Any]:
    _state["enabled"] = bool(flag)
    return {"ok": True, "enabled": _state["enabled"], "peers": _state["peers"]}

def status() -> Dict[str, Any]:
    return {"ok": True, **_state}

def _post_local(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=8.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _broadcast(path: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    res = []
    for host in _state.get("peers", []):
        try:
            res.append(_post_local("/peer/proxy", {"host": host, "path": path, "payload": payload}))
        except Exception as e:
            res.append({"ok": False, "error": str(e)})
    return res

def leader_hotkey(seq: str) -> Dict[str, Any]:
    if not _state.get("enabled"): return {"ok": False, "error": "disabled"}
    pkt = {"type":"hotkey","seq":str(seq or "")}
    return {"ok": True, "peers": _broadcast("/sync/kbd/ingest", pkt)}

def leader_text(value: str) -> Dict[str, Any]:
    if not _state.get("enabled"): return {"ok": False, "error": "disabled"}
    pkt = {"type":"text","value":str(value or "")}
    return {"ok": True, "peers": _broadcast("/sync/kbd/ingest", pkt)}

def follower_ingest(pkt: Dict[str, Any]) -> Dict[str, Any]:
    t = (pkt.get("type") or "").lower()
    # consent gate check
    g = _post_local("/consent/check", {"scope": "full_control"})
    if not g.get("ok") or not g.get("allowed"):
        return {"ok": False, "need_consent": True}
    if t == "hotkey":
        return _post_local("/desktop/window/hotkey", {"seq": pkt.get("seq","")})
    if t == "text":
        # basic falsification - character-by-character input (if the system has a separate endpoint, substitute the adapter for it)
        val = str(pkt.get("value",""))
        ok_all = True
        for ch in val:
            r = _post_local("/desktop/window/type_char", {"ch": ch})
            ok_all = ok_all and bool(r.get("ok"))
        return {"ok": ok_all}
    return {"ok": False, "error": "bad_packet"}