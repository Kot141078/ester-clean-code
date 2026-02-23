# -*- coding: utf-8 -*-
"""
tests/smoke/test_memory_reflection.py

Smoke:
  - modul modules.memory.reflection importiruetsya;
  - run_daily_reflection() vozvraschaet dict (ok True/False ne vazhno).

Mosty:
- Yavnyy: (tests ↔ modules.memory.reflection) — proveryaem sam modul refleksii.
- Skrytyy #1: (Struktura repo ↔ CI) — bootstrap sys.path k kornyu proekta.
- Skrytyy #2: (Refleksiya ↔ Nochnoy tsikl) — nalichie modulya garantiruet gotovnost sloya insaytov.

Zemnoy abzats:
Eto prostoy multimetr: vidim, chto modul na meste i vyzyvaetsya, znachit
nochnaya logika "podumat nad dnem" fizicheski podklyuchena i ne lomaet sborku.
"""
from __future__ import annotations

import os
import sys
import importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Dobavlyaem koren proekta (ester-project) v sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_reflection_import_and_run():
    m = importlib.import_module("modules.memory.reflection")
    assert hasattr(m, "run_daily_reflection")
    res = m.run_daily_reflection(mode="test")  # type: ignore[attr-defined]
    assert isinstance(res, dict)