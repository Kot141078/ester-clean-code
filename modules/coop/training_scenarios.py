# -*- coding: utf-8 -*-
"""modules/coop/training_scenarios.py - paketnyy “start obucheniya”: golos+sinkhro-kursor+pleybek.

Ideaya:
- Odin vyzov zapuskaet: net_playback peers (esli zadany), sync_cursor.enable(True), playlist or interactive_playback.
- Odin vyzov ostanavlivaet vse: otklyuchaet sync_cursor, shlet stop v net_playback i iplay.

API:
- start(spec) -> {started: {...}}
- stop() -> {stopped: {...}}

Format spec:
{
  "peers": ["ip:port"],
  "mode": "iplay|playlist",
  "steps": [...], # dlya iplay
  "playlist": {...} #dlya playlist
}

MOSTY:
- Yavnyy: (Orkestratsiya ↔ UX) vse “poekhalo” odnoy knopkoy.
- Skrytyy #1: (Infoteoriya ↔ Prostota) menshe ruchnykh pereklyucheniy — menshe oshibok.
- Skrytyy #2: (Kibernetika ↔ Role) veduschiy legko menyaet temp obucheniya.

ZEMNOY ABZATs:
Simply proksiruem k suschestvuyuschim REST-ruchkam modular net_playback/sync_cursor/iplay/playlist.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=15.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def start(spec: Dict[str, Any]) -> Dict[str, Any]:
    peers = list(spec.get("peers") or [])
    if peers:
        _post("/netplay/peers", {"peers": peers})
    _post("/sync/peers", {"peers": peers})
    _post("/sync/enable", {"enabled": True, "throttle_ms": 20})
    mode = (spec.get("mode") or "iplay").lower()
    res = {}
    if mode == "iplay":
        _post("/iplay/load", {"steps": list(spec.get("steps") or [])})
        res["iplay"] = _post("/iplay/start", {})
    else:
        res["playlist"] = _post("/playlist/run", {"spec": spec.get("playlist") or {"name":"demo","items":[]}, "peers": peers})
    return {"ok": True, "started": {"peers": peers, "mode": mode, **res}}

def stop() -> Dict[str, Any]:
    res = {}
    res["iplay"] = _post("/iplay/stop", {})
    res["playlist"] = _post("/playlist/stop", {})
    res["sync"] = _post("/sync/enable", {"enabled": False})
    res["net_ctrl"] = _post("/netplay/leader/ctrl", {"op": "stop"})
    return {"ok": True, "stopped": res}