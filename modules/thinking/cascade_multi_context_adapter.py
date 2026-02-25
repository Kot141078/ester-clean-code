
# -*- coding: utf-8 -*-
"""modules/thinking/cascade_multi_context_adapter.py - mnogokontekstnyy kaskad.

Mosty:
- Yavnyy: (cascade_closed ↔ Memory) — zapuskaet kaskady po neskolkim smyslovym kontekstam.
- Skrytyy #1: (Pisaniya/znanie ↔ Planirovanie) — otdelnye traektorii pod tsennostnyy, nauchnyy, inzhenernyy ugly.
- Skrytyy #2: (Kod ↔ Praktika) — kontekst “engineering” podtalkivaet k inzhenernym/sistemnym resheniyam.

A/B-slot:
    ESTER_CASCADE_CTX_AB = "A" | "B"
    A - sovmestimyy rezhim: prosto proksiruet cascade_closed.run_cascade.
    B - rasshirnnyy rezhim: zapuskaet kaskad po neskolkim kontekstam i agregiruet.

Zemnoy abzats:
Inzhener:
    from modules.thinking import cascade_multi_context_adapter as cmc
    res = cmc.run(goal="sproektirovat bezopasnyy servis")
    print(res["summary"])
Tak Ester osmyslyaet tsel kak chelovek: s neskolkikh side (etika, fakty, inzheneriya),
no ostaetsya v svoem closed-box okruzhenii.
# c=a+b"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from modules.thinking import cascade_closed
from modules.thinking import cascade_profile_adapter as cpa
from modules.memory import store
from modules.memory.events import record_event
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_CTX_MODE = (os.environ.get("ESTER_CASCADE_CTX_AB", "A") or "A").strip().upper()


def _contexts() -> List[Dict[str, str]]:
    return [
        {
            "name": "ethics",
            "suffix": "(through the lens of values ​​and consequences for people)",
        },
        {
            "name": "science",
            "suffix": "(through the lens of facts, models and testable assumptions)",
        },
        {
            "name": "engineering",
            "suffix": "(through the prism of architecture, fault tolerance and resource limitations)",
        },
    ]


def run(goal: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Mnogokontekstnyy zapusk kaskada.

    A-rezhim:
        proxy na cascade_closed.run_cascade(goal, params)
    B-rezhim:
        progon po neskolkim kontekstam, sbor summary i profiley."""
    params = params or {}
    if _CTX_MODE != "B":
        base = cascade_closed.run_cascade(goal, params)
        return {
            "ok": True,
            "mode": "A",
            "goal": goal,
            "summary": base.get("summary", ""),
            "variants": [
                {
                    "context": "base",
                    "summary": base.get("summary", ""),
                    "profile": None,
                }
            ],
        }

    variants: List[Dict[str, Any]] = []
    for ctx in _contexts():
        ctx_goal = f"{goal}{ctx['suffix']}"
        casc = cascade_closed.run_cascade(ctx_goal, params)
        prof = cpa.run_and_profile(ctx_goal, params)
        variants.append(
            {
                "context": ctx["name"],
                "goal": ctx_goal,
                "summary": casc.get("summary", ""),
                "profile": prof.get("profile", {}),
            }
        )

    parts = []
    for v in variants:
        p = v.get("profile") or {}
        hint = p.get("human_hint") or v.get("summary", "")
        parts.append(f"[{v['context']}] {hint}")
    summary = " | ".join(parts) if parts else "Mnogokontekstnyy kaskad vypolnen."

    try:
        memory_add(
            "multi_context",
            f"mcascade: {goal}",
            {"summary": summary, "variants": variants},
        )
        record_event("think", "multi-context", True, {"goal": goal})
    except Exception:
        pass

    return {
        "ok": True,
        "mode": "B",
        "goal": goal,
        "summary": summary,
        "variants": variants,
    }