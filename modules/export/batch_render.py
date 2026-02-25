# -*- coding: utf-8 -*-
"""modules/export/batch_render.py - paketnyy render mnozhestva gidov (MP4/bez/s TTS).

Vkhod:
{"jobs":[{"name":"guide_A","text":"Shag A"}, {"name":"guide_B","text":"Shag B"}]}

Rezhim:
- Posledovatelno vyzyvaet modules/export/guide_ffmpeg.make dlya kazhdogo job.
- Vedet prostoy progress v pamyati (status).

MOSTY:
- Yavnyy: (Memory ↔ Proizvodstvo) mnogo stsenariev — odin zapusk.
- Skrytyy #1: (Infoteoriya ↔ Determinizm) odinakovye skripty dlya kazhdoy papki.
- Skrytyy #2: (Inzheneriya ↔ Avtomatizatsiya) podgotovka partiy dlya montazha.

ZEMNOY ABZATs:
Odin potok, lokalno, bez vneshnikh zavisimostey. Polzovatel sam zapuskaet ffmpeg-skripty.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import threading, time
from modules.export.guide_ffmpeg import make
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"running": False, "done": 0, "total": 0, "last": None}

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

def run(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    if _state.get("running"):
        try:
            _mirror_background_event(
                "[BATCH_RENDER_ALREADY_RUNNING]",
                "batch_render",
                "already_running",
            )
        except Exception:
            pass
        return {"ok": False, "error": "already_running"}
    _state.update({"running": True, "done": 0, "total": len(jobs or []), "last": None})
    def _runner():
        try:
            for j in (jobs or []):
                _state["last"] = j
                make(str(j.get("name") or "guide"), str(j.get("text") or ""))
                _state["done"] += 1
        finally:
            _state["running"] = False
            try:
                _mirror_background_event(
                    f"[BATCH_RENDER_DONE] done={_state['done']} total={_state['total']}",
                    "batch_render",
                    "done",
                )
            except Exception:
                pass
    threading.Thread(target=_runner, daemon=True).start()
    try:
        _mirror_background_event(
            f"[BATCH_RENDER_START] total={_state['total']}",
            "batch_render",
            "start",
        )
    except Exception:
        pass
    return {"ok": True, "total": _state["total"]}

def status() -> Dict[str, Any]:
    return {"ok": True, **_state}