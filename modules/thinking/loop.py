# -*- coding: utf-8 -*-
"""
modules/thinking/loop.py — odin takt tsikla agenta: Sense → Think → Plan (bez Act).

Funktsiya:
- step(goal:str, sense_fetcher:callable) -> {"planned":int, "queued":int, "preview":[...]}
  * soberem sense (journal/windows/screen), peredadim v planner.plan()
  * solem v obschuyu ochered (bez vypolneniya)

Khranilische ocheredi — v modules.planner.forge (v pamyati).

MOSTY:
- Yavnyy: (Sensory ↔ Mysl) svyazyvaem A2 i buduschiy A4.
- Skrytyy #1: (Infoteoriya ↔ Diagnostika) vozvrat preview daet prozrachnost prinyatiya resheniya.
- Skrytyy #2: (Inzheneriya ↔ Sovmestimost) step ne trebuet consent i ne imeet pobochnykh effektov.

ZEMNOY ABZATs:
Taktovyy vyzov statichen i determinirovanen: tolko formirovanie spiska shagov.
Ispolnenie poyavitsya v A4.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, Callable
from modules.planner.forge import plan as _plan, merge_queue as _merge, queue as _queue
from modules.sense.collect import journal_tail, windows_list, screen_snap
from modules.thinking.memory_bridge import integrate
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def step(goal:str)->Dict[str,Any]:

    plan={"goal":goal,"steps":[]}
    if goal:
        # Emulyatsiya prostogo planirovaniya
        plan["steps"]=[{"op":"think","text":f"Obdumyvayu tsel: {goal}"}]
    # integratsiya pamyati
    plan=integrate(goal,plan)
    return {"ok":True,"planned":len(plan.get("steps",[])),"plan":plan}


def _sense() -> Dict[str, Any]:
    j = journal_tail(100)
    w = windows_list()
    s = screen_snap(0,0)
    return {"journal": j, "windows": w, "screen": s}

def step(goal: str, sense_fetcher: Callable[[], Dict[str, Any]] | None = None) -> Dict[str, Any]:
    sense = (sense_fetcher or _sense)()
    chain = _plan(goal, sense)
    planned = len(chain)
    queued = _merge(chain) if planned else len(_queue())
    return {"ok": True, "planned": planned, "queued": queued, "preview": chain}