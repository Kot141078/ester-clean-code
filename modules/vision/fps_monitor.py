# -*- coding: utf-8 -*-
"""
modules/vision/fps_monitor.py — izmerenie chastoty obnovleniya «sensora ekrana».

Rezhim:
- start(target="screen"|"window", window_id?:int, seconds:int=3)
- stop()
- status() -> {running, fps_avg, samples}

Realizatsiya: sinkhronnyy tsikl zakhvata (bez demona po umolchaniyu); start zapuskaet fonovoy potok, kotoryy
N sekund vyzyvaet sootvetstvuyuschiy zakhvat i meryaet srednee. Ostanovka — dobrovolnaya.

MOSTY:
- Yavnyy: (Sensor ↔ Ekspluatatsiya) vidim realnuyu chastotu signala.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) podbor tempa deystviy pod realnyy FPS.
- Skrytyy #2: (Kibernetika ↔ Kontrol) izmeryaem → nastraivaem profil.

ZEMNOY ABZATs:
Polezno dlya igr/demonstratsiy: ne strelyaem klikami bystree, chem obnovlyaetsya kartinka.

# c=a+b
"""
from __future__ import annotations
import threading, time
from typing import Optional, Dict, Any, Callable

from modules.ops.window_ops import capture_by_id
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state = {"thr": None, "fps": 0.0, "samples": 0, "running": False}

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

def _get_screen_png_b64() -> bool:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=3.0)
    conn.request("GET", "/desktop/rpa/screen")
    resp = conn.getresponse()
    ok = (resp.status == 200)
    conn.read()  # vychistit
    conn.close()
    return ok

def _worker(target: str, window_id: Optional[int], seconds: int):
    _state["running"] = True
    t_end = time.time() + max(1, int(seconds))
    cnt = 0
    last = time.time()
    while time.time() < t_end and _state.get("running"):
        ok = False
        if target == "screen":
            ok = _get_screen_png_b64()
        elif target == "window" and window_id:
            ok = bool(capture_by_id(window_id))
        if ok:
            cnt += 1
    dur = max(1e-3, time.time() - last)
    _state["fps"] = float(cnt / dur)
    _state["samples"] = cnt
    _state["running"] = False
    try:
        _mirror_background_event(
            f"[FPS_MON_DONE] fps={_state['fps']:.2f} samples={cnt}",
            "fps_monitor",
            "done",
        )
    except Exception:
        pass

def start(target: str = "screen", window_id: Optional[int] = None, seconds: int = 3) -> None:
    if _state.get("running"): return
    thr = threading.Thread(target=_worker, args=(target, window_id, seconds), daemon=True)
    _state["thr"] = thr; _state["running"] = True; _state["fps"] = 0.0; _state["samples"] = 0
    thr.start()
    try:
        _mirror_background_event(
            f"[FPS_MON_START] target={target} seconds={seconds}",
            "fps_monitor",
            "start",
        )
    except Exception:
        pass

def stop() -> None:
    _state["running"] = False
    try:
        _mirror_background_event(
            "[FPS_MON_STOP]",
            "fps_monitor",
            "stop",
        )
    except Exception:
        pass

def status() -> Dict[str, Any]:
    return {"running": bool(_state.get("running")), "fps_avg": float(_state.get("fps", 0.0)), "samples": int(_state.get("samples", 0))}