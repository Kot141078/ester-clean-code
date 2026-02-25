# -*- coding: utf-8 -*-
"""modules/garage/planner.py — razlozhenie rabot proekta na zadachi flota.

Mosty:
- Yavnyy: (Garazh ↔ Flot) prevraschaem potrebnosti proekta v ispolnimye zadaniya.
- Skrytyy #1: (Volya ↔ Avtonomiya) ekshen mozhet zapuskatsya “po svoey vole” (for example, na dedlayn).
- Skrytyy #2: (Memory ↔ Profile) fiksiruem plan/otpravku zadach v pamyat.

Zemnoy abzats:
Eto kak plan rabot na stene garazha: razbili tsel na shagi i razvesili zadaniya po masteram.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def make_plan(project_id: str)->List[Dict[str,Any]]:
    """Returns a list of specials for Fleet:
    - create a mini-site
    - pack spare parts"""
    return [
        {"kind":"site_build","title":"Build project site","args":{"project_id": project_id, "theme":"clean"},"tags":["general"],"cost":0.01},
        {"kind":"zip_export","title":"Export ZIP","args":{"project_id": project_id},"tags":["general"],"cost":0.01}
    ]
# c=a+b