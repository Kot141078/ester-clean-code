# -*- coding: utf-8 -*-
"""routes/roles_edges_routes.py - REST nad grafom affinnosti.

MOSTY:
- (Yavnyy) POST /roles/edges/observe - fiksiruem ko-aktivnost (most iz lyubykh istochnikov).
- (Skrytyy #1) GET /roles/edges/team_affinity - deshevyy raschet bonusa dlya komandy.
- (Skrytyy #2) Kontekst sobytiya khranitsya v JSON, prigoden dlya obyasnimosti/bordy.

ZEMNOY ABZATs:
Dali znat, chto lyudi rabotali ryadom - i sistema nachala uchityvat “pritertost”, ne navyazyvaya zhestkikh pravil.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, FastAPI, Body, Query
from fastapi.responses import JSONResponse
from roles.edges import add_edge, team_affinity
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

@router.post("/roles/edges/observe")
async def roles_edges_observe(payload: Dict[str, Any] = Body(...)):
    agents = payload.get("agents") or []
    context = payload.get("context") or {}
    weight = float(payload.get("weight") or 1.0)
    if not agents or len(agents) < 2:
        return JSONResponse({"ok": False, "error": "agents>=2 required"}, status_code=400)
    n = add_edge([str(x) for x in agents], context=context, weight=weight)
    return JSONResponse({"ok": True, "edges_updated": n})

@router.get("/roles/edges/team_affinity")
async def roles_team_affinity(agents: str = Query("")):
    arr = [a for a in (agents or "").split(",") if a]
    return JSONResponse({"ok": True, "affinity": round(team_affinity(arr), 4)})

def mount_roles_edges(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app