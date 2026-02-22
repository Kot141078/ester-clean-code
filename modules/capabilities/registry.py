# -*- coding: utf-8 -*-
"""
modules/capabilities/registry.py — samodeklaratsii vozmozhnostey + avtoinventar.

Mosty:
- Yavnyy: (Samosoznanie ↔ UX) spisok «chto ya umeyu» dlya voli/polzovatelya.
- Skrytyy #1: (Inzheneriya ↔ Inventar) skaniruet routes/* i actions.
- Skrytyy #2: (Planirovanie ↔ Energiya) mozhno stroit plany ot dostupnykh primitivov.

Zemnoy abzats:
Kak rezyume: deystviya, marshruty i opisaniya — v odnom meste, obnovlyaemo.

# c=a+b
"""
from __future__ import annotations
import os, json, pkgutil, importlib
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("CAP_REG_DB","data/cap/capabilities.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"declared":{}, "auto":{}}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def declare(name: str, kind: str, desc: str) -> Dict[str,Any]:
    _ensure()
    j=json.load(open(DB,"r",encoding="utf-8"))
    j["declared"][name]={"kind": kind, "desc": desc}
    json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True}

def _scan_routes() -> List[str]:
    mods=[]
    for _, name, _ in pkgutil.iter_modules(["routes"]):
        if name.endswith("_routes"):
            mods.append(f"/{name.replace('_routes','')}")
    return mods

def _scan_actions() -> List[str]:
    try:
        from modules.thinking.action_registry import list_actions  # type: ignore
        return [a.get("name") for a in (list_actions() or [])]
    except Exception:
        return []

def list_caps() -> Dict[str,Any]:
    _ensure()
    j=json.load(open(DB,"r",encoding="utf-8"))
    auto={"routes": _scan_routes(), "actions": _scan_actions()}
    j["auto"]=auto
    json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, **j}
# c=a+b