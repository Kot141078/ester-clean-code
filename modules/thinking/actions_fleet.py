# -*- coding: utf-8 -*-
"""modules/thinking/actions_fleet.py - eksheny “voli” dlya flota i garazha.

Mosty:
- Yavnyy: (Mysli ↔ Flot) volya mozhet zapuskat naznachenie i tik vorkera.
- Skrytyy #1: (Ostorozhnost ↔ Podskazki) submit vozvraschaet hint pro HTTP+pilyulyu.
- Skrytyy #2: (Garazh ↔ Plan) generate plan i otpravlyaem zadachi.

Zemnoy abzats:
Brain govorit: “raskiday zadachi” - i flot nachinaet dvizhenie; “sdelay shag” - i vorkery berut naryady.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def a_assign(args: Dict[str,Any]):
        from modules.fleet.core import assign_tick
        return assign_tick()
    register("fleet.assign.tick", {}, {"ok":"bool"}, 5, a_assign)

    def a_worker(args: Dict[str,Any]):
        from modules.fleet.worker import tick
        return tick()
    register("fleet.worker.tick", {}, {"ok":"bool","got":"int"}, 6, a_worker)

    def a_submit(args: Dict[str,Any]):
        # Directly sets tasks through HTTP (under the pill)
        return {"ok": True, "hint":"use /fleet/task/submit with pill", "spec": args.get("spec")}
    register("fleet.task.submit", {"spec":"dict"}, {"ok":"bool"}, 2, a_submit)

    def a_garage_plan(args: Dict[str,Any]):
        from modules.garage.planner import make_plan
        from modules.fleet.core import submit_task
        pid=str(args.get("project_id",""))
        plan=make_plan(pid)
        results=[]
        for spec in plan:
            results.append(submit_task(spec))
        return {"ok": all(r.get("ok") for r in results), "submitted": results}
    register("garage.plan.submit", {"project_id":"str"}, {"ok":"bool"}, 12, a_garage_plan)

_reg()
# c=a+b