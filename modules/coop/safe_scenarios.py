# -*- coding: utf-8 -*-
"""modules/coop/safe_scenarios.py - seyf-stsenarii (atomarnye shagi s proverkoy i otkatom).

Format steps:
{
  "title": "Otkryt menyu",
  "do": {"type":"hotkey","seq":"ALT+F"},
  "check":{"kind":"ocr_contains","text":"Fayl","timeout_ms":4000},
  "undo": {"type":"hotkey","seq":"ESC"} #optsionalno
}

Performance:
- Vypolnyaem shagi po poryadku. Esli proverka provalena - po steku otkatyvaem vse proshedshie shagi (esli zadan undo).
- V zhurnal /attention/journal/append pishem sobytiya: safe_step_ok / safe_step_fail / safe_rollback.
- Status khranitsya v module.

MOSTY:
- Yavnyy: (Control ↔ Nadezhnost) lyubye deystviya - s vstroennoy strakhovkoy.
- Skrytyy #1: (Infoteoriya ↔ Diagnostika) zhurnal daet fakty “where upalo”.
- Skrytyy #2: (Inzheneriya ↔ UX) stsenarii ispolzuyut te zhe primitivy, chto interaktivnyy pleybek.

ZEMNOY ABZATs:
Nikakikh novykh kontraktov: vse cherez suschestvuyuschie ruchki /desktop/* i /attention/journal/*.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"running": False, "index": 0, "rolled_back": False, "last_error": None}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=15.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _do_action(act: Dict[str, Any]) -> Dict[str, Any]:
    t = (act.get("type") or "").lower()
    if t == "hotkey":
        return _post("/desktop/window/hotkey", {"seq": act.get("seq","")})
    if t == "mix_apply":
        return _post("/profiles/mix/apply", {"title": act.get("title","")})
    if t == "workflow":
        return _post("/rpa/workflows/run", {"name": act.get("name","")})
    if t == "mouse":
        return _post("/desktop/window/mouse_move", {"x": int(act.get("x",0)), "y": int(act.get("y",0))})
    return {"ok": False, "error": "unknown_action"}

def _check(chk: Dict[str, Any]) -> bool:
    if not chk: return True
    to = int(chk.get("timeout_ms", 3000))
    t0 = time.time()
    while (time.time()-t0)*1000 <= max(100, to):
        scr = _get("/desktop/rpa/screen")
        if not scr.get("ok"): time.sleep(0.2); continue
        png = scr.get("png_b64","")
        if (chk.get("kind") or "") == "ocr_contains":
            r = _post("/desktop/rpa/ocr_contains", {"png_b64": png, "needle": chk.get("text",""), "lang": chk.get("lang","eng+rus")})
            if r.get("ok") and r.get("found"): return True
        elif (chk.get("kind") or "") == "template_match":
            r = _post("/desktop/vision/template/find", {"screen_b64": png, "template_b64": chk.get("template_b64",""), "threshold": float(chk.get("threshold",0.78))})
            if r.get("ok"): return True
        time.sleep(0.2)
    return False

def run(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    _state.update({"running": True, "index": 0, "rolled_back": False, "last_error": None})
    done_stack: List[Dict[str, Any]] = []
    for i, st in enumerate(steps or []):
        _state["index"] = i
        _do_action(st.get("do") or {})
        ok = _check(st.get("check") or {})
        if ok:
            _post("/attention/journal/append", {"event":"safe_step_ok","detail":{"index":i,"title":st.get("title","")}})
            done_stack.append(st)
            continue
        # proval → otkat
        _state["last_error"] = {"index": i, "title": st.get("title","")}
        for j, prev in enumerate(reversed(done_stack)):
            un = prev.get("undo") or {}
            if un: _do_action(un)
        _state["rolled_back"] = True
        _state["running"] = False
        _post("/attention/journal/append", {"event":"safe_step_fail","detail":_state["last_error"]})
        _post("/attention/journal/append", {"event":"safe_rollback","detail":{"count": len(done_stack)}})
        return {"ok": False, **status()}
    _state["running"] = False
    return {"ok": True, **status()}

def status() -> Dict[str, Any]:
    return {"ok": True, "running": bool(_state.get("running")), "index": int(_state.get("index",0)), "rolled_back": bool(_state.get("rolled_back")), "last_error": _state.get("last_error")}