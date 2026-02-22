# -*- coding: utf-8 -*-
"""
modules.sys — proksi k vstroennomu sys (dlya sovmestimosti starogo koda).

MOSTY:
- Yavnyy: (routy, kotorye delayut import modules.sys as sys ↔ nastoyaschiy sys) — proksiruem atributy.
- Skrytyy #1: (Sovmestimost) predostavlyaem pole modules = builtin_sys.modules.
- Skrytyy #2: (Bezopasnost) tolko delegirovanie, bez pobochnykh effektov.

ZEMNOY ABZATs:
Esli gde-to pereputali put importa, eto «perekhodnik» — vse ravno popadem v nastoyaschiy sys.

# c=a+b
"""
from __future__ import annotations
import sys as _sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def __getattr__(name: str):
    return getattr(_sys, name)

# Klyuchevaya sovmestimost: ozhidanie polya modules
modules = _sys.modules  # type: ignore[assignment]

# c=a+b