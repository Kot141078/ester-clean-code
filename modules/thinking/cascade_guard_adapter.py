# -*- coding: utf-8 -*-
"""
modules/thinking/cascade_guard_adapter.py — zaschita ot zatsiklivaniya kaskada.

Mosty:
- Yavnyy: (Zapusk kaskadov ↔ Ogranicheniya) — vvodit proverku pered zapuskom slozhnykh kaskadov.
- Skrytyy #1: (Volya ↔ Resursnost) — ne daet odnoy tseli szhech CPU beskonechnymi perezapuskami.
- Skrytyy #2: (Kaskad ↔ Prozrachnost) — fiksiruet prichinu propuska v strukture otveta.

A/B-slot:
    ESTER_CASCADE_GUARD_AB = "A" | "B"
    A — vyklyucheno (sovmestimost).
    B — vklyuchaet proverku chastoty i kolichestva zapuskov per-goal.

Zemnoy abzats:
    from modules.thinking import cascade_guard_adapter as cga
    from modules.thinking import cascade_closed
    res = cga.wrap_run(cascade_closed.run_cascade, "slozhnaya tsel")
    print(res["summary"] if res.get("ok") else res["reason"])
# c=a+b
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_GUARD_MODE = (os.environ.get("ESTER_CASCADE_GUARD_AB", "A") or "A").strip().upper()

_MAX_RUNS_PER_GOAL = int(os.environ.get("ESTER_CASCADE_GUARD_MAX_RUNS", "10") or "10")
_COOLDOWN_SEC = float(os.environ.get("ESTER_CASCADE_GUARD_COOLDOWN", "5") or "5")

# goal -> { "last_ts": float, "runs": float }
_stats: Dict[str, Dict[str, float]] = {}


def _now() -> float:
    return time.time()


def _can_run(goal: str) -> bool:
    if _GUARD_MODE != "B":
        return True
    st = _stats.get(goal)
    now = _now()
    if not st:
        _stats[goal] = {"last_ts": now, "runs": 1}
        return True
    runs = st.get("runs", 0)
    last_ts = st.get("last_ts", 0.0)
    if runs >= _MAX_RUNS_PER_GOAL:
        return False
    if (now - last_ts) < _COOLDOWN_SEC:
        return False
    st["runs"] = runs + 1
    st["last_ts"] = now
    return True


def wrap_run(
    func: Callable[[str, Dict[str, Any] | None], Dict[str, Any]],
    goal: str,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Bezopasnyy zapusk kaskada s uchetom guard.

    - V rezhime A: prosto vyzyvaet func(goal, params).
    - V rezhime B: proveryaet chastotu zapuskov i mozhet vernut otkaz s reason.
    """
    if _GUARD_MODE != "B":
        return func(goal, params or {})

    if not _can_run(goal):
        return {
            "ok": False,
            "skipped": True,
            "reason": "guard: too_frequent_or_too_many_runs",
            "goal": goal,
        }

    return func(goal, params or {})