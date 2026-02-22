# -*- coding: utf-8 -*-
"""
modules/vision/misrec_guard.py — avto-stop pri serii neuspeshnykh raspoznavaniy.

Parametry:
- window: razmer okna poslednikh popytok (N)
- max_fails: dopustimoe chislo neudach v okne (M)

API:
- set_policy(window:int, max_fails:int) -> ok
- report(success:bool) — soobschit o rezultate popytki (OCR/Template)
- status() -> {blocked:bool, fails:int, window:int, max_fails:int}
- reset()

MOSTY:
- Yavnyy: (Nadezhnost ↔ Kontrol) seriya promakhov — «tormoz».
- Skrytyy #1: (Infoteoriya ↔ Diagnostika) prozrachno vidno, pochemu blok.
- Skrytyy #2: (Kibernetika ↔ Bezopasnost) zaschischaet ot «uleta» v nevernye kliki.

ZEMNOY ABZATs:
Prostoy schetchik v pamyati, optsionalno vyzyvaetsya iz OCR/Template-koda i triggerov.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"window": 5, "max_fails": 3, "arr": []}

def set_policy(window: int, max_fails: int) -> Dict[str, Any]:
    _state["window"] = max(1, int(window))
    _state["max_fails"] = max(1, int(max_fails))
    _state["arr"] = []
    return {"ok": True, **status()}

def report(success: bool) -> Dict[str, Any]:
    arr: List[int] = list(_state.get("arr", []))
    arr.append(1 if success else 0)
    if len(arr) > _state["window"]:
        arr = arr[-_state["window"]:]
    _state["arr"] = arr
    return {"ok": True, **status()}

def status() -> Dict[str, Any]:
    arr: List[int] = list(_state.get("arr", []))
    fails = int(arr.count(0))
    blocked = fails >= int(_state.get("max_fails", 3))
    return {"ok": True, "blocked": blocked, "fails": fails, "window": int(_state.get("window")), "max_fails": int(_state.get("max_fails"))}

def reset() -> Dict[str, Any]:
    _state["arr"] = []
    return {"ok": True, **status()}