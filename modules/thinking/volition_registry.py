# -*- coding: utf-8 -*-
"""
modules/thinking/volition_registry.py — reestr volevykh impulsov dlya myshleniya.

Mosty:
- Yavnyy: (Volya ↔ Myshlenie) — tsentralizovannyy spisok tseley dlya avtonomnogo osmysleniya.
- Skrytyy #1: (Impulsy ↔ Memory) — impulsy mogut rozhdatsya iz sobytiy pamyati ili vneshnikh marshrutov.
- Skrytyy #2: (Bezopasnost ↔ Avtomatizm) — rezhim A gasit lyubye pobochnye effekty.

A/B-slot:
  ESTER_VOLITION_MODE = "A" | "B"
    A (defolt): impulsy ignoriruyutsya (povedenie kak ranshe).
    B: impulsy stavyatsya v ochered i mogut byt obrabotany modules.always_thinker.

Zemnoy abzats:
    from modules.thinking import volition_registry
    volition_registry.add_impulse({"goal": "peresobrat nedelnyy otchet"})
# c=a+b
"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_VOLITION_MODE = (os.environ.get("ESTER_VOLITION_MODE", "A") or "A").strip().upper()

_impulses: List[Dict[str, Any]] = []
_lock = threading.Lock()


def add_impulse(impulse: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dobavit volevoy impuls.

    Bezopasnost:
    - V rezhime A (defolt) impuls ne aktiviruetsya (vozvrat ignored=True).
    - V rezhime B impuls pomeschaetsya v ochered.
    """
    if _VOLITION_MODE != "B":
        return {"ok": False, "ignored": True}
    if not isinstance(impulse, dict):
        return {"ok": False, "error": "impulse must be dict"}
    goal = impulse.get("goal")
    if not goal:
        return {"ok": False, "error": "missing goal"}
    with _lock:
        _impulses.append({"goal": str(goal), "meta": impulse.get("meta") or {}})
        size = len(_impulses)
    return {"ok": True, "count": size}


def get_next_impulse() -> Optional[Dict[str, Any]]:
    """Poluchit sleduyuschiy impuls (ili None)."""
    if _VOLITION_MODE != "B":
        return None
    with _lock:
        if not _impulses:
            return None
        return _impulses.pop(0)


def pending_count() -> int:
    """Tekuschee kolichestvo ozhidayuschikh impulsov."""
    with _lock:
        return len(_impulses)