# -*- coding: utf-8 -*-
"""modules/thinking/registry_introspect.py - bezopasnaya introspektsiya reestra ekshenov mysli.

Mosty:
- Yavnyy: (Mysli ↔ Operatsii) pozvolyaet uvidet, kakie eksheny dostupny i s kakimi skhemami.
- Skrytyy #1: (Ostorozhnost ↔ Pilyuli) ruchnoy zapusk ekshena - tolko pod “pilyuley”.
- Skrytyy #2: (Ekonomika ↔ CostFence) zapusk ne obkhodit byudzhetirovanie (ispolzuet shtatnyy invoke).

Zemnoy abzats:
Spisok “instrumentov v yaschike” i vozmozhnost akkuratno nazhat na knopku.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def list_actions() -> Dict[str,Any]:
    try:
        from modules.thinking.action_registry import list_actions as _list  # type: ignore
        return {"ok": True, "actions": _list()}
    except Exception:
        # Fullback: it is unknown how the registry is structured - return the minimum
        return {"ok": False, "error":"action_registry_unavailable"}

def run_action(name: str, args: Dict[str,Any] | None = None) -> Dict[str,Any]:
    try:
        from modules.thinking.action_registry import invoke  # type: ignore
        return invoke(name, dict(args or {}))
    except Exception as e:
        return {"ok": False, "error": str(e)}
# c=a+b