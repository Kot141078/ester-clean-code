# -*- coding: utf-8 -*-
"""modules/p2p/filter.py — obertka nad Bloom dlya REST: add/check/state.

Mosty:
- Yavnyy: (REST ↔ Bloom) konvertiruet zaprosy v prostye operatsii filtra.
- Skrytyy #1: (Mesh ↔ Piringi) uzhe ispolzuetsya v Mesh submit/pull.
- Skrytyy #2: (Profile ↔ Prozrachnost) mozhno pomechat setevye sobytiya.

Zemnoy abzats:
Tonkaya prosloyka: “dobavit id” and “verify id” - vse, chto nuzhno dlya prilichnogo setevogo povedeniya.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def check(ids: List[str])->Dict[str,Any]:
    from modules.p2p.bloom import check as _check  # lazy import
    return _check(list(ids or []))

def add(ids: List[str])->Dict[str,Any]:
    from modules.p2p.bloom import add as _add
    return _add(list(ids or []))

def state()->Dict[str,Any]:
    from modules.p2p.bloom import _load as _load
    j=_load()
    return {"ok": True, "m": j["m"], "k": j["k"], "bits_len": len(j["bits"])}
# c=a+b