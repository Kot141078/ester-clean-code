# -*- coding: utf-8 -*-
"""modules/stream/macro_recorder.py - makrorekorder “iz zhivogo potoka” → safe-stsenariy.

Ideaya:
- Arm: podpisyvaemsya logicheski (flag) i nachinaem pisat sobytiya: hotkey, type_char, mouse_move/click.
- Disarm: ostanavlivaem zapis.
- Preview: konvertiruem sobytiya v shagi (do) + minimalnye proverki (check) po evristikam.
- Export safe: add undo (cherez undo_suggester.patch) i vydaem polnotsennyy safe JSON.

Evristiki:
- CTRL+S → check: OCR "Save|Save"
- ALT+F → check: "Fayl|File"
- mouse_click → check: empty (ostavlyaem na polzovatelya), no shag sokhranyaem
- type_text → check: po fragmentu teksta (pervye 5 simvolov)

MOSTY:
- Yavnyy: (Memory ↔ Deystvie) prevraschaem realnuyu sessiyu v vosproizvodimyy stsenariy.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) check po klyuchevym slovam snizhaet lozhnye makrosy.
- Skrytyy #2: (Inzheneriya ↔ UX) bezopasnyy eksport srazu v format seyf-stsenariev.

ZEMNOY ABZATs:
Nikakikh khukov OS — ispolzuem uzhe suschestvuyuschie REST-ruchki i nash flag zapisi.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
from modules.coop.undo_suggester import patch as _patch
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"armed": False, "events": []}

def arm() -> Dict[str, Any]:
    _state["armed"] = True; _state["events"] = []
    return {"ok": True}

def disarm() -> Dict[str, Any]:
    _state["armed"] = False
    return {"ok": True, "count": len(_state["events"])}

def record(ev: Dict[str, Any]) -> Dict[str, Any]:
    if not _state.get("armed"):
        return {"ok": False, "error": "not_armed"}
    _state["events"].append(ev)
    return {"ok": True}

def _to_steps(evts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    steps = []
    for e in evts:
        t = (e.get("type") or "").lower()
        if t == "hotkey":
            seq = e.get("seq","")
            title = f"Hotkey {seq}"
            chk = {}
            if "CTRL+S" in seq.upper():
                chk = {"kind":"ocr_contains","text":"Sokhran", "lang":"eng+rus", "timeout_ms":3000}
            elif "ALT+F" in seq.upper():
                chk = {"kind":"ocr_contains","text":"Fayl", "lang":"eng+rus", "timeout_ms":3000}
            steps.append({"title": title, "do": {"type":"hotkey","seq":seq}, "check": chk})
        elif t == "type_text":
            val = str(e.get("value",""))
            steps.append({"title":"Vvod teksta", "do":{"type":"text","value":val}, "check":{"kind":"ocr_contains","text": val[:5], "lang":"eng+rus", "timeout_ms":3000}})
        elif t == "mouse_click":
            steps.append({"title":"Klik", "do":{"type":"mouse","x":int(e.get("x",0)),"y":int(e.get("y",0))}, "check":{}})
    return steps

def preview() -> Dict[str, Any]:
    return {"ok": True, "steps": _to_steps(list(_state.get("events") or []))}

def export_safe() -> Dict[str, Any]:
    pv = preview()
    patched = _patch(pv["steps"])
    return {"ok": True, "steps": patched.get("steps", pv["steps"])}