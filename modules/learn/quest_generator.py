# -*- coding: utf-8 -*-
"""
modules/learn/quest_generator.py — avtogeneratsiya «uchebnykh kvestov» iz zhurnala polzovatelya.

Ideya:
- Parsim /attention/journal (N poslednikh zapisey), gruppiruem po patternam deystviy:
  * zapusk prilozheniya / pereklyuchenie okna
  * rabota s menyu / sokhranenie / eksport
- Formiruem kvesty: nazvanie, tseli (check), shagi (safe-stsenarii s undo), kriterii zaversheniya.

API:
- mine(N=300) -> chernovik kvestov
- preview()   -> svodka po naydennym kvestam
- export()    -> JSON paketa kvestov (dlya trenirovki/delezha)

MOSTY:
- Yavnyy: (Memory ↔ Obuchenie) lichnaya istoriya → personalnye missii.
- Skrytyy #1: (Infoteoriya ↔ Repraktika) tseli — te, chto uzhe vstrechalis i vosproizvodimy.
- Skrytyy #2: (Inzheneriya ↔ UX) vydaem srazu v formate safe-stsenariev.

ZEMNOY ABZATs:
Chistaya rabota s JSON-zhurnalom, nikakikh setevykh i vneshnikh zavyazok.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"draft": []}

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _safe_step(title: str, do: Dict[str, Any], check_text: str) -> Dict[str, Any]:
    return {
        "title": title,
        "do": do,
        "check": {"kind":"ocr_contains","text": check_text, "lang":"eng+rus", "timeout_ms": 3000},
        "undo": {"type":"hotkey","seq":"ESC"}
    }

def _group(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    quests = []
    # Primitivnye evristiki:
    # 1) esli vstrechaetsya ALT+F (menyu Fayl) → kvest "Otkryt i sokhranit"
    saw_file = any((it.get("detail") or {}).get("title","").lower().find("menyu")>=0 or 
                   (it.get("detail") or {}).get("seq","").upper()=="ALT+F" 
                   for it in items if it.get("event") in ("iplay_step","safe_step_ok"))
    if saw_file:
        quests.append({
            "name": "Otkryt i sokhranit",
            "goals": ["Otkryt menyu 'Fayl'", "Save dokument"],
            "steps": [
                _safe_step("Otkryt menyu", {"type":"hotkey","seq":"ALT+F"}, "Fayl"),
                _safe_step("Save", {"type":"hotkey","seq":"CTRL+S"}, "Save")
            ]
        })
    # 2) eksport/eksport v PDF — po slovam «Eksport»/«Export»
    saw_export = any(str((it.get("detail") or {}).get("title","")).lower().find("eksport")>=0 
                     for it in items if it.get("event") in ("iplay_step","safe_step_ok"))
    if saw_export:
        quests.append({
            "name": "Eksport v PDF",
            "goals": ["Otkryt eksport", "Podtverdit eksport PDF"],
            "steps": [
                _safe_step("Otkryt eksport", {"type":"hotkey","seq":"CTRL+E"}, "Eksport"),
                _safe_step("Podtverdit", {"type":"hotkey","seq":"ENTER"}, "PDF")
            ]
        })
    return quests

def mine(N: int = 300) -> Dict[str, Any]:
    j = _get(f"/attention/journal/list?n={int(max(50,N))}")
    items = list(j.get("items") or [])
    quests = _group(items)
    _state["draft"] = quests
    return {"ok": True, "count": len(quests), "quests": quests}

def preview() -> Dict[str, Any]:
    return {"ok": True, "count": len(_state.get("draft", [])), "names": [q.get("name") for q in _state.get("draft", [])]}

def export() -> Dict[str, Any]:
    return {"ok": True, "quests": list(_state.get("draft", []))}