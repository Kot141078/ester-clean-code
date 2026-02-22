
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.voice — minimalnaya golosovaya obvyazka.
Mosty:
- Yavnyy: say()/transcribe()/devices() s bezopasnymi defoltami.
- Skrytyy #1: (DX ↔ Offlayn) — nikakikh vneshnikh zavisimostey.
- Skrytyy #2: (Integratsiya ↔ UI) — predskazuemye otvety dlya paneley.

Zemnoy abzats:
Dazhe bez audiobibliotek sistema dolzhna «derzhat litso»: vozvraschat validnye otvety i ne padat.
# c=a+b
"""
from typing import Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def say(text: str, voice: str | None = None) -> Dict:
    return {"ok": True, "synth": False, "voice": voice or "default", "text": text}

def transcribe(path: str) -> Dict:
    return {"ok": True, "text": "", "note": "noop transcribe"}

def devices() -> List[Dict]:
    return [{"name": "default", "id": "default", "type": "virtual"}]