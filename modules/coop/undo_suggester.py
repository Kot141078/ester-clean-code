# -*- coding: utf-8 -*-
"""modules/coop/undo_suggester.py - avto-predlozhenie undo dlya shagov.

Vkhod: steps (iz interaktiva/seyf-stsenariya), where u nekotorykh net "undo".
Rules (evristiki, lokalno):
- do.type=="hotkey" -> undo={"type":"hotkey","seq":"ESC"}
- do.type=="workflow" name=N -> undo={"type":"workflow","name": N+"_undo"} (informativnaya podskazka)
- do.type=="mix_apply" title=T -> undo={"type":"mix_apply","title":"<previous>"} (esli est v meta.prev_title)
- do.type=="mouse" -> undo kak "mouse" v iskhodnuyu tochku (iz meta.prev_point)

API:
- suggest(steps) -> {"suggested":[indexes]}
- patch(steps) -> vernet steps s dobavlennymi undo po evristikam (ne pishet on disk)

MOSTY:
- Yavnyy: (Logika ↔ Nadezhnost) kazhdomu deystviyu — spas-shag.
- Skrytyy #1: (Memory ↔ Praktika) opiraetsya na meta proshlykh znacheniy, esli predostavleny.
- Skrytyy #2: (Inzheneriya ↔ UX) bystryy avtopodbor, dalshe — ruchnaya korrektirovka.

ZEMNOY ABZATs:
Nikakikh vneshnikh zavisimostey, JSON na vkhod/vykhod.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _mk_undo(do: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any] | None:
    t = (do.get("type") or "").lower()
    if t == "hotkey":
        return {"type":"hotkey","seq":"ESC"}
    if t == "workflow":
        n = str(do.get("name",""))
        return {"type":"workflow","name": (n+"_undo") if n else ""}
    if t == "mix_apply":
        prev = (meta or {}).get("prev_title")
        if prev: return {"type":"mix_apply","title": prev}
        return {"type":"hotkey","seq":"ESC"}
    if t == "mouse":
        p = (meta or {}).get("prev_point")
        if isinstance(p, dict) and "x" in p and "y" in p:
            return {"type":"mouse","x": int(p["x"]), "y": int(p["y"])}
        return {"type":"hotkey","seq":"ESC"}
    return None

def suggest(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    idx = []
    for i, st in enumerate(steps or []):
        if st.get("undo"): 
            continue
        do = st.get("do") or st.get("action") or {}
        su = _mk_undo(do, st.get("meta") or {})
        if su: idx.append(i)
    return {"ok": True, "suggested": idx}

def patch(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    out = []
    patched = []
    for i, st in enumerate(steps or []):
        st2 = dict(st)
        if not st2.get("undo"):
            do = st2.get("do") or st2.get("action") or {}
            su = _mk_undo(do, st2.get("meta") or {})
            if su:
                st2["undo"] = su
                patched.append(i)
        out.append(st2)
    return {"ok": True, "patched": patched, "steps": out}