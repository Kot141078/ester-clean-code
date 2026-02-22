# -*- coding: utf-8 -*-
"""
modules/ops/control_state.py — globalnaya «pauza/SOS» dlya deystviy Ester.

Sostoyanie: data/security/control_state.json {"paused": false}
API: get_paused(), set_paused(True/False)

Integratsiya: routy deystviy (RPA/makrosy) dolzhny prezhde proveryat flag i vozvraschat 423 (Locked), esli pauza aktivna.

MOSTY:
- Yavnyy: (Volya ↔ Bezopasnost) mgnovennaya ostanovka vsekh aktov.
- Skrytyy #1: (Kibernetika ↔ Kontrol) zavedomaya «krasnaya knopka».
- Skrytyy #2: (Anatomiya ↔ Psikhologiya) kak refleks otdergivaniya ruki.

ZEMNOY ABZATs:
Fayl/flag — prostoy i nadezhnyy. Bez demonov. Otmenyaet buduschie deystviya do snyatiya.

# c=a+b
"""
from __future__ import annotations
import os, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
PATH = os.path.join(ROOT, "data", "security")
FILE = os.path.join(PATH, "control_state.json")

def _ensure():
    os.makedirs(PATH, exist_ok=True)
    if not os.path.exists(FILE):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump({"paused": False}, f)

def get_paused() -> bool:
    _ensure()
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            return bool((json.load(f) or {}).get("paused", False))
    except Exception:
        return False

def set_paused(v: bool) -> None:
    _ensure()
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump({"paused": bool(v)}, f, ensure_ascii=False, indent=2)