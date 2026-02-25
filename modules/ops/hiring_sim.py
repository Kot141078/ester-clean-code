# -*- coding: utf-8 -*-
"""modules/ops/hiring_sim.py - “mikro-naym”: formiruem skoup roli/taskov/kriteriev bez realnogo onbordinga.

Mosty:
- Yavnyy: (Operatsii ↔ Lyudi) gotovim opisanie roli i chek-list zadach.
- Skrytyy #1: (Infoteoriya ↔ Kontrol) kriterii kachestva i metriki dlya priemki.
- Skrytyy #2: (Ekonomika ↔ Byudzhet) vpisyvaem potolok oplaty v obschiy byudzhet.

Zemnoy abzats:
Eto tekhnicheskoe zadanie na podrabotku: chto delat, kak merit result, skolko mozhno potratit.

# c=a+b"""
from __future__ import annotations
import time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def scope(role: str, tasks: List[str], budget_cap: float) -> Dict[str, Any]:
    if not role.strip(): return {"ok": False, "error":"role required"}
    if budget_cap < 0: budget_cap = 0.0
    metrics = [{"name":"timeliness","desc":"v srok, %"}, {"name":"quality","desc":"review rating 0..1"}, {"name":"completeness","desc":"tasks completed, %"}]
    return {
        "ok": True,
        "ts": int(time.time()),
        "role": role,
        "tasks": [{"title": t, "acceptance":["proydeno revyu","chek-list zakryt"]} for t in (tasks or [])],
        "budget_cap": budget_cap,
        "metrics": metrics,
        "note": "publish manually on freelance/volunteer platforms; PDN/secrets - prohibited"
    }