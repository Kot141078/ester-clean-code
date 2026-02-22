"""
"""
from __future__ import annotations

# -*- coding: utf-8 -*-
"""
modules/thinking/will_scheduler_adapter.py — planirovschik voli dlya kaskadnogo myshleniya.

Mosty:
- Yavnyy: (volition_registry/priority ↔ cascade_closed) — vybiraet, kakoy impuls dumat sleduyuschim.
- Skrytyy #1: (priority_adapter ↔ guard_adapter) — sochetaet vazhnost i zaschitu ot zatsiklivaniya.
- Skrytyy #2: (Volya ↔ always_thinker) — predostavlyaet gotovuyu funktsiyu, prigodnuyu dlya fonovogo vorkera.

A/B-slot:
    ESTER_WILL_SCHED_AB = "A" | "B"
    A — minimalnoe vmeshatelstvo: odin impuls → odin kaskad.
    B — rasshirennyy rezhim: prioritizatsiya, guard, mnogokontekstnyy kaskad.

Zemnoy abzats:
Inzhener:
    from modules.thinking import will_scheduler_adapter as ws
    print(ws.process_next())
Tak mozhno zapuskat «volevoe myshlenie» vruchnuyu ili iz demona.
# c=a+b
"""
import os
from typing import Any, Dict, Optional

from modules.thinking import cascade_closed
from modules.thinking import cascade_guard_adapter as cga
from modules.memory.events import record_event
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.thinking import volition_registry
except Exception:  # pragma: no cover
    volition_registry = None  # type: ignore

try:
    from modules.thinking import volition_priority_adapter as vpa
except Exception:  # pragma: no cover
    vpa = None  # type: ignore

try:
    from modules.thinking import cascade_multi_context_adapter as cmc
except Exception:  # pragma: no cover
    cmc = None  # type: ignore


_SCHED_MODE = (os.environ.get("ESTER_WILL_SCHED_AB", "A") or "A").strip().upper()


def _pull_impulse() -> Dict[str, Any]:
    """
    Poluchit sleduyuschiy impuls s uchetom rezhima.

    A:
        volition_registry.get_next_impulse()
    B:
        vpa.get_next_weighted() esli dostupen,
        inache volition_registry.get_next_impulse()
    """
    if not volition_registry or not hasattr(volition_registry, "get_next_impulse"):
        return {"ok": False, "note": "volition_registry not available"}

    if _SCHED_MODE != "B" or not vpa or not hasattr(vpa, "get_next_weighted"):
        imp = volition_registry.get_next_impulse()
        return {"ok": True, "impulse": imp}

    imp = vpa.get_next_weighted()
    return {"ok": True, "impulse": imp}


def _run_for_goal(goal: str) -> Dict[str, Any]:
    """
    Zapusk kaskada dlya tseli s uchetom guard i mnogokontekstnogo rezhima.
    """
    def base_runner(g: str, p: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if _SCHED_MODE == "B" and cmc and hasattr(cmc, "run"):
            mc = cmc.run(g, p or {})
            return {
                "ok": True,
                "goal": g,
                "multi": True,
                "summary": mc.get("summary", ""),
                "raw": mc,
            }
        return cascade_closed.run_cascade(g, p or {})

    res = cga.wrap_run(base_runner, goal, {})
    return res


def process_next() -> Dict[str, Any]:
    """
    Obrabotat sleduyuschiy volevoy impuls.

    Vozvrat:
      {
        "ok": bool,
        "processed": bool,
        "skipped": bool,
        ...
      }
    """
    pulled = _pull_impulse()
    if not pulled.get("ok"):
        return {"ok": False, "processed": False, "error": pulled.get("note", "no-impulse-backend")}

    imp = pulled.get("impulse")
    if not imp:
        return {"ok": True, "processed": False, "skipped": True, "reason": "no_impulse"}

    goal = imp.get("goal") or "(neizvestnaya tsel)"
    res = _run_for_goal(goal)

    if not res.get("ok") and res.get("skipped"):
        try:
            record_event("will", "guard-skip", True, {"goal": goal})
        except Exception:
            pass
        return {
            "ok": True,
            "processed": False,
            "skipped": True,
            "reason": res.get("reason", "guard-skip"),
        }

    try:
        record_event("will", "processed", True, {"goal": goal})
    except Exception:
        pass

    return {
        "ok": True,
        "processed": True,
        "skipped": False,
        "goal": goal,
        "result": res,
    }