# -*- coding: utf-8 -*-
"""
modules/coop/migrate_to_safe.py — migratsiya starykh stsenariev (action-only) v «seyf-stsenarii».

Vkhod: steps starogo vida, naprimer:
[
  {"title":"Otkryt menyu","action":{"type":"hotkey","seq":"ALT+F"}},
  {"title":"Save","action":{"type":"hotkey","seq":"CTRL+S"}}
]

Pravila:
- action -> do (bez izmeneniy).
- Esli net check: sozdaem OCR-check po pervomu slovu title (esli est) s timeout_ms=3000.
- Esli net undo: ispolzuem modules.coop.undo_suggester.patch dlya avtopodstanovki (ESC/return workflows/...).

API:
- preview(steps) -> {"steps":[...]}   # ne menyaem vkhod
- export(steps)  -> {"steps":[...]}   # itogovaya versiya (safe) s undo i check

MOSTY:
- Yavnyy: (Evolyutsiya ↔ Nadezhnost) perevodim starye stsenarii v atomarnye s otkatom.
- Skrytyy #1: (Memory ↔ Praktika) sokhranyaem smysl shagov, dobavlyaya zaschitnye konstruktsii.
- Skrytyy #2: (Inzheneriya ↔ UX) prostaya knopka «konvertirovat» — nikakoy boli migratsiy.

ZEMNOY ABZATs:
Chistyy JSON-transformer; opiraetsya na uzhe napisannyy undo_suggester.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
from modules.coop.undo_suggester import patch as _patch
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _mk_check(title: str) -> Dict[str, Any]:
    w = (title or "").strip().split()
    if not w: 
        return {}
    return {"kind":"ocr_contains","text": w[0], "lang":"eng+rus", "timeout_ms": 3000}

def preview(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    out = []
    for st in (steps or []):
        s = {"title": st.get("title","")}
        do = st.get("do") or st.get("action") or {}
        s["do"] = do
        if not st.get("check"):
            s["check"] = _mk_check(s["title"])
        else:
            s["check"] = st["check"]
        if st.get("undo"):
            s["undo"] = st["undo"]
        out.append(s)
    return {"ok": True, "steps": out}

def export(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    pv = preview(steps)
    # avtodobavim undo, gde net
    patched = _patch(pv["steps"])
    return {"ok": True, "steps": patched.get("steps", pv["steps"])}