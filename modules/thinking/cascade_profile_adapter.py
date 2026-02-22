# -*- coding: utf-8 -*-
"""
modules/thinking/cascade_profile_adapter.py — profil kaskadnogo myshleniya.

Mosty:
- Yavnyy: (cascade_closed ↔ Memory) — oformlyaet rezultaty kaskada v strukturirovannyy profil.
- Skrytyy #1: (Kaskad ↔ Monitoring) — daet chislovye metriki glubiny i razvetvleniya.
- Skrytyy #2: (Kaskad ↔ Chelovek) — podgotavlivaet chelovekochitaemoe rezyume traektorii mysli.

Zemnoy abzats:
    from modules.thinking import cascade_profile_adapter as cpa
    res = cpa.run_and_profile("kak zhit dalshe")
    print(res["profile"]["human_hint"])
# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, List

from modules.thinking import cascade_closed
from modules.memory import store
from modules.memory.events import record_event
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _complexity_score(steps: List[Dict[str, Any]]) -> float:
    stages = {s.get("stage") for s in steps}
    branches = 0
    acts = 0
    for s in steps:
        if s.get("stage") == "branch":
            branches += len(s.get("candidates") or [])
        if s.get("stage") == "act":
            acts += len(s.get("results") or [])
    score = 0.0
    score += len(stages) * 1.0
    score += min(branches, 10) * 0.3
    score += min(acts, 10) * 0.2
    return round(score, 2)


def _human_hint(goal: str, score: float, steps: List[Dict[str, Any]]) -> str:
    has_branch = any(s.get("stage") == "branch" for s in steps)
    has_reflect = any(s.get("stage") == "reflect" for s in steps)
    if score < 2.0:
        return f"Mysli po tseli «{goal}» byli kratkimi; mozhno uglubit kaskad ili proverit dannye."
    if not has_branch:
        return f"Dlya tseli «{goal}» ne bylo realnogo vetvleniya; stoit rassmotret alternativy."
    if has_branch and has_reflect:
        return f"Dlya tseli «{goal}» otrabotan kaskad s vetvleniem i refleksiey; kartina blizka k chelovecheskomu obdumyvaniyu."
    return f"Tsel «{goal}» obrabotana, no refleksiya ogranichena; mozhno dobavit esche odin prokhod."


def run_and_profile(goal: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Zapuskaet cascade_closed.run_cascade i stroit profil.

    Vozvraschaet:
      {
        "ok": True,
        "goal": str,
        "cascade": {...},
        "profile": {...}
      }
    """
    res = cascade_closed.run_cascade(goal, params or {})
    steps: List[Dict[str, Any]] = list(res.get("steps") or [])
    stages = [s.get("stage") for s in steps]
    score = _complexity_score(steps)
    hint = _human_hint(goal, score, steps)

    profile = {
        "goal": goal,
        "stages": stages,
        "steps_count": len(steps),
        "complexity_score": score,
        "human_hint": hint,
        "summary": res.get("summary", ""),
    }

    try:
        memory_add("think_profile", f"profile: {goal}", {"profile": profile})
        record_event("think", "profile", True, {"goal": goal, "score": score})
    except Exception:
        pass

    return {"ok": True, "goal": goal, "cascade": res, "profile": profile}