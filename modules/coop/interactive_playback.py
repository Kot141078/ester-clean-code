# -*- coding: utf-8 -*-
"""modules/coop/interactive_playback.py - interaktivnyy pleybek stsenariev (s pauzami/proverkami).

Spetsifikatsiya shaga:
{
  "title": "Otkryt menyu",
  "action": {"type":"hotkey","seq":"ALT+F"},
  "check": {"kind":"ocr_contains","text":"Fayl","lang":"rus+eng"}, #optsionalno
  "timeout_ms": 5000
}

API (module):
- load(spec:list[steps])
- start(), pause(), resume(), stop(), next(), prev(), status()
- integriruet /desktop/rpa/screen, /desktop/rpa/ocr_contains, /desktop/vision/template/find,
  a dlya deystviy - /desktop/window/hotkey or /profiles/mix/apply.

MOSTY:
- Yavnyy: (Obuchenie ↔ Deystvie) poshagovo, s proverkoy facta.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) taymauty, yavnye usloviya prokhozhdeniya.
- Skrytyy #2: (Kibernetika ↔ Sovmestnost) to zhe mozhet idti na peers cherez uzhe imeyuschiesya mekhanizmy.

ZEMNOY ABZATs:
Odin potok v protsesse; nikakikh fonovykh demonov. Stsenariy - obychnyy JSON.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import threading, time, http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"steps": [], "i": 0, "running": False, "paused": False, "last": None}

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

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
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

def load(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    _state.update({"steps": list(steps or []), "i": 0})
    return {"ok": True, "count": len(_state["steps"])}

def _check(check: Dict[str, Any], timeout_ms: int) -> bool:
    """Returns Three if the check is successful, False if there is a timeout/error."""
    if not check: return True
    t0 = time.time()
    while (time.time()-t0)*1000.0 <= max(100, timeout_ms or 1000):
        scr = _get("/desktop/rpa/screen")
        if not scr.get("ok"): time.sleep(0.2); continue
        png = scr.get("png_b64","")
        kind = (check.get("kind") or "").lower()
        if kind == "ocr_contains":
            r = _post("/desktop/rpa/ocr_contains", {"png_b64": png, "needle": check.get("text",""), "lang": check.get("lang","eng+rus")})
            if r.get("ok") and r.get("found"): return True
        elif kind == "template_match":
            r = _post("/desktop/vision/template/find", {"screen_b64": png, "template_b64": check.get("template_b64",""), "threshold": float(check.get("threshold", 0.78))})
            if r.get("ok"): return True
        time.sleep(0.2)
    return False

def _do_action(act: Dict[str, Any]) -> Dict[str, Any]:
    t = (act.get("type") or "").lower()
    if t == "hotkey":
        return _post("/desktop/window/hotkey", {"seq": act.get("seq","")})
    if t == "mix_apply":
        return _post("/profiles/mix/apply", {"title": act.get("title","")})
    if t == "workflow":
        return _post("/rpa/workflows/run", {"name": act.get("name","")})
    return {"ok": False, "error": "unknown_action"}

def _runner():
    _state["running"] = True; _state["paused"] = False
    while _state["running"] and _state["i"] < len(_state["steps"]):
        if _state["paused"]: time.sleep(0.1); continue
        st = _state["steps"][_state["i"]]
        _state["last"] = {"index": _state["i"], "title": st.get("title","")}
        act = st.get("action") or {}
        chk = st.get("check") or {}
        to  = int(st.get("timeout_ms", 3000))
        _do_action(act)
        ok = _check(chk, to)
        _post("/attention/journal/append", {"event":"iplay_step","detail":{"index":_state['i'],"title":st.get("title",""),"ok":ok}})
        if not ok:
            try:
                _mirror_background_event(
                    f"[IPLAY_STEP_FAIL] idx={_state['i']} title={st.get('title','')}",
                    "interactive_playback",
                    "step_fail",
                )
            except Exception:
                pass
        _state["i"] += 1
    _state["running"] = False

def start() -> Dict[str, Any]:
    if _state.get("running"): return {"ok": True, "running": True}
    thr = threading.Thread(target=_runner, daemon=True); thr.start()
    try:
        _mirror_background_event(
            "[IPLAY_START]",
            "interactive_playback",
            "start",
        )
    except Exception:
        pass
    return {"ok": True, "running": True}

def pause() -> Dict[str, Any]:
    _state["paused"] = True
    try:
        _mirror_background_event(
            "[IPLAY_PAUSE]",
            "interactive_playback",
            "pause",
        )
    except Exception:
        pass
    return {"ok": True, "paused": True}

def resume() -> Dict[str, Any]:
    _state["paused"] = False
    try:
        _mirror_background_event(
            "[IPLAY_RESUME]",
            "interactive_playback",
            "resume",
        )
    except Exception:
        pass
    return {"ok": True, "paused": False}

def stop() -> Dict[str, Any]:
    _state["running"] = False
    try:
        _mirror_background_event(
            "[IPLAY_STOP]",
            "interactive_playback",
            "stop",
        )
    except Exception:
        pass
    return {"ok": True, "running": False}

def next_step() -> Dict[str, Any]:
    _state["i"] = min(len(_state["steps"]), _state["i"] + 1); return {"ok": True, "i": _state["i"]}

def prev_step() -> Dict[str, Any]:
    _state["i"] = max(0, _state["i"] - 1); return {"ok": True, "i": _state["i"]}

def status() -> Dict[str, Any]:
    return {"ok": True, "running": bool(_state.get("running")), "paused": bool(_state.get("paused")), "index": int(_state.get("i",0)), "last": _state.get("last")}