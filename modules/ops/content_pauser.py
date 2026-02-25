# -*- coding: utf-8 -*-
"""modules/ops/content_pauser.py - “pauza po kontentu” dlya triggerov/pleybufera.

Conditions:
- FPS < min_fps (if not available in /desktop/metrics)
- require_visible=true i window svernuto/neaktivno (if dostupno cherez /desktop/window/status)
- manual_pause=true (hand tumbler)

API:
- set_policy(min_fps:int|null, require_visible:bool, manual_pause:bool)
- get_status() -> {allowed:bool, reason?:str, metrics?:...}

MOSTY:
- Yavnyy: (Wednesday ↔ Deystvie) plokhie usloviya — stop.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) izmeryaem i obyasnyaem prichinu.
- Skrytyy #2: (Kibernetika ↔ Kontrol) prostoy brake dlya lyubykh avto-deystviy.

ZEMNOY ABZATs:
Legkaya proverka, nikakikh demonov. Ispolzuetsya triggerami/vatcherom cherez REST.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, Optional
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"min_fps": None, "require_visible": False, "manual_pause": False}

def set_policy(min_fps: Optional[int], require_visible: bool, manual_pause: bool) -> Dict[str, Any]:
    _state["min_fps"] = (int(min_fps) if (min_fps is not None and str(min_fps)!='') else None)
    _state["require_visible"] = bool(require_visible)
    _state["manual_pause"] = bool(manual_pause)
    return {"ok": True, **_state}

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=5.0)
    conn.request("GET", path)
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def get_status() -> Dict[str, Any]:
    if _state["manual_pause"]:
        return {"ok": True, "allowed": False, "reason": "manual_pause"}
    # FPS
    fps_ok = True
    fps_val = None
    m = _get("/desktop/metrics")
    if m.get("ok"):
        fps_val = m.get("fps")
        if _state["min_fps"] is not None and isinstance(fps_val, (int, float)):
            if float(fps_val) < float(_state["min_fps"]):
                fps_ok = False
    # visible
    vis_ok = True
    if _state["require_visible"]:
        st = _get("/desktop/window/status")
        if st.get("ok"):
            vis_ok = bool(st.get("active", True) and not st.get("minimized", False))
    allowed = fps_ok and vis_ok
    reason = None
    if not allowed:
        reason = "fps_low" if not fps_ok else "not_visible"
    return {"ok": True, "allowed": allowed, "reason": reason, "metrics": {"fps": fps_val}}