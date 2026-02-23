# -*- coding: utf-8 -*-
"""
routes/assign_hints_routes.py - podskazki dlya naznacheniy na baze profiley i (optsionalno) grafa.

MOSTY:
- (Yavnyy) /synergy/assign/hints → otdaet ranzhirovannyy spisok kandidatov s poyasneniyami, ne menyaya osnovnoy orchestrator.
- (Skrytyy #1) Mozhet uchityvat graf vzaimodeystviy (ASSIGN_HINTS_USE_GRAPH=1) kak bonus «sygrannosti».
- (Skrytyy #2) Signaly berutsya iz roles.store i roles.graph, tak chto eto chistyy add-on sloy.

ZEMNOY ABZATs:
Eto «podskazchik»: podskazyvaet, kto luchshe spravitsya i s kem im budet legche rabotat - bez vmeshatelstva v osnovnoy planirovschik.

# c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Dict, List
from fastapi import APIRouter, FastAPI, Body
from fastapi.responses import JSONResponse

from roles.store import rank_for_task, list_people
from roles.graph import cohesion_bonus_for
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

@router.post("/synergy/assign/hints")
async def assign_hints(payload: Dict[str, Any] = Body(...)):
    task_text = str(payload.get("task_text") or "")
    dims = payload.get("dims") or {}
    top_n = int(payload.get("top_n") or 5)
    with_agent = payload.get("with_agent")  # esli nuzhno podobrat «v paru» k konkretnomu agentu
    base = rank_for_task(task_text if task_text else None, dims, top_n=1000)

    use_graph = (os.getenv("ASSIGN_HINTS_USE_GRAPH","1") == "1")
    if use_graph and with_agent:
        for row in base:
            row["score"] = float(row["score"]) + 0.1 * cohesion_bonus_for(with_agent, row["agent_id"])

    base.sort(key=lambda x: x["score"], reverse=True)
    ranked = base[:max(1, top_n)]
    return JSONResponse({"ok": True, "ranked": ranked, "considered": len(base), "used_graph": use_graph})

def mount_assign_hints(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app