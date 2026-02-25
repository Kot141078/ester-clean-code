# -*- coding: utf-8 -*-
"""R8/services/sec/path_guard.py - bezopasnaya skleyka putey i validatsiya otnositelnykh putey.

Mosty:
- Yavnyy: Enderton — spetsifikatsiya safe_join kak predikat: result.startswith(base) ∧ ne soderzhit traversal.
- Skrytyy #1: Ashbi — prostoy regulyator: zapreschaem opasnye posledovatelnosti, logiruem otkloneniya.
- Skrytyy #2: Cover & Thomas - snizhaem neopredelennost: edinaya funktsiya, vmesto mnozhestva “kak-nibud”.

Zemnoy abzats (inzheneriya):
Ispolzovat pered zapisyu faylov bandla/otchetov. Only stdlib. Vozvraschaet normalizovannyy put or brosaet ValueError.

# c=a+b"""
from __future__ import annotations
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def safe_join(base: str, rel: str) -> str:
    base = os.path.abspath(base)
    cand = os.path.abspath(os.path.join(base, rel))
    # prohibitions going beyond the base and hidden reference elements
    bad = any(p in ("..",) for p in rel.replace("\\", "/").split("/"))
    if bad or not cand.startswith(base):
        raise ValueError(f"unsafe path: {rel}")
    return cand

# c=a+b