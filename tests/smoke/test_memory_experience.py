# -*- coding: utf-8 -*-
"""
tests/smoke/test_memory_experience.py

Smoke:
  - modul modules.memory.experience importiruetsya;
  - build_experience_profile() i sync_experience() suschestvuyut;
  - obe funktsii vozvraschayut dict.

Mosty:
- Yavnyy: (tests ↔ experience) — garantiruem rabotosposobnost sloya opyta.
- Skrytyy #1: (CI ↔ struktura repo) — bootstrap kornya proekta.
- Skrytyy #2: (Opyt ↔ son/refleksiya) — daem signal, chto verkhniy sloy pamyati podklyuchen.

Zemnoy abzats:
Esli etot test zelenyy — u Ester est tekhnicheski validnyy sloy "opyta",
dazhe esli poka on pustoy iz-za otsutstviya insaytov.
"""
from __future__ import annotations

import os
import sys
import importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_experience_import_and_api():
    m = importlib.import_module("modules.memory.experience")
    assert hasattr(m, "build_experience_profile")
    assert hasattr(m, "sync_experience")

    profile = m.build_experience_profile()
    assert isinstance(profile, dict)

    sync_res = m.sync_experience(mode="test")
    assert isinstance(sync_res, dict)