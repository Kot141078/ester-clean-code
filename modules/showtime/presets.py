# -*- coding: utf-8 -*-
"""modules/showtime/presets.py - nabor gotovykh demonstratsionnykh stsenariev ("showtime presets").

Funktsii:
- list_presets() -> spisok dostupnykh nazvaniy
- get_plan(name:str) -> plan deystviy (tot zhe format, chto u planner.forge.plan)
- run_preset(name:str) -> generate plan, kladet v ochered, zapuskaet /agent/run

MOSTY:
- Yavnyy: (Plan ↔ Demonstratsiya) fiksirovannye shablony pozvolyayut mgnovenno pokazat povedenie agenta.
- Skrytyy #1: (Infoteoriya ↔ UX) stabilnye stsenarii dlya obucheniya i testov.
- Skrytyy #2: (Inzheneriya ↔ Ekspluatatsiya) nikakikh vneshnikh zavisimostey, offlayn.

ZEMNOY ABZATs:
Presety - eto prosto zaranee sostavlennye plany, ispolzuemye kak “primery” dlya trenirovki i pokaza Ester.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json
from modules.planner.forge import merge_queue, clear
from modules.act import runner
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PRESETS: Dict[str, List[Dict[str, Any]]] = {
    "Notepad demo": [
        {"op":"hotkey","args":{"keys":"WIN+R"}},
        {"op":"type","args":{"text":"notepad"}},
        {"op":"hotkey","args":{"keys":"ENTER"}},
        {"op":"ensure_focus","args":{"app_like":"Notepad"}},
        {"op":"type","args":{"text":"Esther shows the steps. Hello Ovner!"}},
        {"op":"hotkey","args":{"keys":"CTRL+S"}},
        {"op":"save_as","args":{"path":"%USERPROFILE%\\Desktop\\demo_ester.txt"}},
        {"op":"hotkey","args":{"keys":"ENTER"}}
    ],
    "TextEdit demo": [
        {"op":"hotkey","args":{"keys":"CMD+SPACE"}},
        {"op":"type","args":{"text":"TextEdit"}},
        {"op":"hotkey","args":{"keys":"ENTER"}},
        {"op":"ensure_focus","args":{"app_like":"TextEdit"}},
        {"op":"hotkey","args":{"keys":"CMD+N"}},
        {"op":"type","args":{"text":"Ester pishet v TextEdit."}},
        {"op":"hotkey","args":{"keys":"CMD+S"}},
        {"op":"save_as","args":{"path":"~/Desktop/demo_ester.txt"}},
        {"op":"hotkey","args":{"keys":"ENTER"}}
    ],
    "Browser demo": [
        {"op":"open_app","args":{"app_like":"browser"}},
        {"op":"type","args":{"text":"https://example.com"}},
        {"op":"hotkey","args":{"keys":"ENTER"}}
    ]
}

def list_presets() -> List[str]:
    return sorted(_PRESETS.keys())

def get_plan(name: str) -> List[Dict[str, Any]]:
    return _PRESETS.get(name, [])

def run_preset(name: str) -> Dict[str, Any]:
    plan = get_plan(name)
    if not plan:
        return {"ok": False, "error": f"unknown preset {name}"}
    clear()
    merge_queue(plan)
    # Vypolnit cherez lokalnyy vyzov runner.run()
    res = runner.run(max_steps=len(plan), step_timeout_ms=4000)
    return {"ok": bool(res.get("ok")), "name": name, "result": res}