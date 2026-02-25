# -*- coding: utf-8 -*-
"""Visualizer - generatsiya prostykh ASCII-skhem dlya planov/grafov.

Mosty:
- Yavnyy: (Myshlenie ↔ Vizualnaya rech) - plan deystviy prevraschaetsya v prostuyu chitaemuyu diagrammu.
- Skrytyy 1: (UX ↔ Obyasnimost) - odin vzglyad na skhemu ekonomit chtenie dlinnogo teksta.
- Skrytyy 2: (Memory ↔ Doklady) — schemy mozhno klast v otchety/logi dlya post-fakta analysis.

Zemnoy abzats:
Sometimes luchshe "odna kartinka". Dazhe esli net GUI - ASCII-skhema v konsoli ili HTML bystro daet strukturu."""
from __future__ import annotations

import os
from typing import List, Dict, Any

from modules.meta.ab_warden import ab_switch
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def render_plan(title: str, steps: List[str]) -> Dict[str, Any]:
    """Slot A — bazovyy pryamoy potok →.
    Slot B - dobavlyaet kontrolnye tochki i masshtabiruyuschuyu ramku."""
    steps = [s.strip() for s in steps if s and str(s).strip()]
    if not steps:
        steps = ["Collect", "Judge", "Act", "Review"]
    with ab_switch("VIZ") as slot:
        line = " → ".join(steps)
        box = [
            f"┌── {title.strip() or 'Plan'} ─────────────────────────────┐",
            f"│ {line[:56]:<56} │",
            "└──────────────────────────────────────────────────────────┘",
        ]
        if slot == "B":
            box.insert(1, "│ checkpoints: start • mid • end                         │")
        return {"ok": True, "slot": slot, "ascii": "\n".join(box)}

# finalnaya stroka
# c=a+b