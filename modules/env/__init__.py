
# -*- coding: utf-8 -*-
"""
modules.env — tonkaya obertka nad peremennymi okruzheniya.
Mosty:
- Yavnyy: get()/set()/get_bool().
- Skrytyy #1: (Bezopasnost ↔ DX) — edinaya tochka dostupa.
- Skrytyy #2: (Inzheneriya ↔ Testy) — udobno mokat.

Zemnoy abzats:
Edinoe obraschenie k ENV snizhaet rassypanie po kodu.
# c=a+b
"""
from __future__ import annotations
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
def get(key: str, default=None): return os.getenv(key, default)
def set(key: str, value: str): os.environ[key] = value; return True
def get_bool(key: str, default=False):
    v = os.getenv(key)
    if v is None: return default
    return v not in {"0","false","False",""}