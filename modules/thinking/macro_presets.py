# -*- coding: utf-8 -*-
"""modules/thinking/macro_presets.py - presety makrosov/vorkflou dlya populyarnykh prilozheniy.

Soderzhimoe:
- preset_notepad_intro -> wf_preset_notepad_intro
- preset_chrome_search -> wf_preset_chrome_search
- preset_file_explorer_nav -> wf_preset_explorer_nav

Kazhdyy preset - JSON workflow sovmestimyy s suschestvuyuschim ispolnitelem (rpa_workflows).

MOSTY:
- Yavnyy: (Znanie ↔ Deystvie) gotovye stsenarii bez programmirovaniya.
- Skrytyy #1: (Infoteoriya ↔ UX) edinyy format dlya avtogeneratsii instruktsiy.
- Skrytyy #2: (Kibernetika ↔ Memory) standartnye “patterny klikov” sokhranyayutsya kak vosproizvodimye tsepochki.

ZEMNOY ABZATs:
Faylov net - presety otdayutsya v slovare i installiruyutsya v data/workflows/*.json po zaprosu.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def list_presets() -> Dict[str, Any]:
    return {
        "preset_notepad_intro": {
            "name": "wf_preset_notepad_intro",
            "steps": [
                {"macro": "open_portal_and_type", "args": {"app": "notepad", "text": ""}},
                {"macro": "type_text", "args": {"text": "Hello! This is Notepad.\nStep 1: Enter text.\nStep 2: save."}},
                {"macro": "send_hotkey", "args": {"seq": "CTRL+S"}}
            ]
        },
        "preset_chrome_search": {
            "name": "wf_preset_chrome_search",
            "steps": [
                {"macro": "open_portal_and_type", "args": {"app": "chrome", "text": ""}},
                {"macro": "type_text", "args": {"text": "what is ester virtual desk?"}},
                {"macro": "send_hotkey", "args": {"seq": "ENTER"}}
            ]
        },
        "preset_file_explorer_nav": {
            "name": "wf_preset_explorer_nav",
            "steps": [
                {"macro": "open_portal_and_type", "args": {"app": "explorer", "text": ""}},
                {"macro": "type_text", "args": {"text": "C:\\\\Ester\\\\logs"}},
                {"macro": "send_hotkey", "args": {"seq": "ENTER"}}
            ]
        }
    }