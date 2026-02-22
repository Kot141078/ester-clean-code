# -*- coding: utf-8 -*-
"""
modules/coop/attention_playlist.py — pleylisty vnimaniya (serii strelok/boksov po taymeru).

Struktura pleylista:
{
  "name": "demo",
  "items": [
    {"kind":"arrow","from":[300,200],"to":[420,240],"label":"Shag 1","delay_ms":1000},
    {"kind":"box","box":{"left":100,"top":120,"width":220,"height":80},"label":"Shag 2","delay_ms":1000}
  ],
  "loop": false
}

API (modul):
- run(spec, peers:list[str]) -> proigrat posledovatelnost (lokalno + peers cherez /stream/overlay/*)
- stop(), status()

MOSTY:
- Yavnyy: (Orkestratsiya ↔ Vnimanie) seriya podskazok vmesto odinochnykh.
- Skrytyy #1: (Infoteoriya ↔ UX) konkretnyy temp i poryadok.
- Skrytyy #2: (Kibernetika ↔ Sovmestnost) u vsekh uchastnikov odinakovaya rezhissura.

ZEMNOY ABZATs:
Odin potok proigryvaniya; kadry berem iz /desktop/rpa/screen; nalozhenie delaem /stream/overlay/*.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import threading, time, http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"thr": None, "running": False, "name": None, "index": 0}

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

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=6.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _broadcast(peers: List[str], kind: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    out=[]
    for host in peers or []:
        out.append(_post("/peer/proxy", {"host": host, "path": f"/stream/overlay/{kind}", "payload": payload}))
    return out

def _step_play(item: Dict[str, Any], peers: List[str]) -> Dict[str, Any]:
    scr = _get("/desktop/rpa/screen")
    if not scr.get("ok"):
        try:
            _mirror_background_event(
                "[ATTN_PLAYLIST_SCREEN_FAIL]",
                "attention_playlist",
                "screen_fail",
            )
        except Exception:
            pass
        return {"ok": False, "error": "screen_failed"}
    png = scr.get("png_b64","")
    if item.get("kind") == "arrow":
        payload = {"png_b64": png, "from": item.get("from"), "to": item.get("to"), "label": item.get("label","")}
        loc = _post("/stream/overlay/arrow", payload)
        peer = _broadcast(peers, "arrow", payload)
    else:
        payload = {"png_b64": png, "box": item.get("box"), "label": item.get("label","")}
        loc = _post("/stream/overlay/box", payload)
        peer = _broadcast(peers, "box", payload)
    _post("/attention/journal/append", {"event":"playlist_step", "detail":{"item": item}})
    return {"ok": True, "local": loc, "peers": peer}

def _runner(spec: Dict[str, Any], peers: List[str]):
    _state.update({"running": True, "name": spec.get("name"), "index": 0})
    items = list(spec.get("items") or [])
    loop = bool(spec.get("loop", False))
    try:
        while _state["running"]:
            for i, it in enumerate(items):
                if not _state["running"]: break
                _state["index"] = i
                _step_play(it, peers)
                time.sleep(max(0.01, (it.get("delay_ms") or 1000) / 1000.0))
            if not loop: break
    finally:
        _state.update({"running": False})

def run(spec: Dict[str, Any], peers: List[str]|None=None) -> Dict[str, Any]:
    if _state.get("running"):
        try:
            _mirror_background_event(
                "[ATTN_PLAYLIST_ALREADY_RUNNING]",
                "attention_playlist",
                "already_running",
            )
        except Exception:
            pass
        return {"ok": False, "error": "already_running"}
    thr = threading.Thread(target=_runner, args=(spec, list(peers or [])), daemon=True)
    _state["thr"] = thr; thr.start()
    try:
        _mirror_background_event(
            f"[ATTN_PLAYLIST_START] name={spec.get('name','playlist')}",
            "attention_playlist",
            "start",
        )
    except Exception:
        pass
    return {"ok": True, "name": spec.get("name","playlist")}

def stop() -> Dict[str, Any]:
    _state["running"] = False
    try:
        _mirror_background_event(
            "[ATTN_PLAYLIST_STOP]",
            "attention_playlist",
            "stop",
        )
    except Exception:
        pass
    return {"ok": True}

def status() -> Dict[str, Any]:
    return {"ok": True, "running": bool(_state.get("running")), "name": _state.get("name"), "index": _state.get("index", 0)}