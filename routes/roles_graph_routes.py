# -*- coding: utf-8 -*-
"""
routes/roles_graph_routes.py - REST-nadstroyka dlya grafa i selektivnykh utochneniy.

MOSTY:
- (Yavnyy) /roles/graph/edge, /roles/graph/neighbors/{agent_id} - upravlenie grafom.
- (Skrytyy #1) /roles/clarify/candidates - vybiraet profili s vysokoy neopredelennostyu (ROLE_UNCERTAINTY_THR).
- (Skrytyy #2) Ne trebuet pravok v rolyakh/soobscheniyakh - eto dobavochnyy sloy.

ZEMNOY ABZATs:
Utochnyaem redko i po delu - tolko kogda profilya nedostatochno. Tak my «uchimsya ot lyudey», ne prevraschayas v anketu.

# c=a+b
"""
from __future__ import annotations

import os, math, time
from typing import Any, Dict, List
from fastapi import APIRouter, FastAPI, Body
from fastapi.responses import JSONResponse

from roles.graph import touch_edge, neighbors
from roles.store import list_people
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

def _uncertainty(vec: Dict[str,float]) -> float:
    # prostaya mera: 1 - srednyaya "uverennost" po ne nulevym osyam
    if not vec: return 1.0
    vals = [abs(v) for v in vec.values()]
    return max(0.0, 1.0 - sum(vals)/ (len(vals) or 1))

@router.post("/roles/graph/edge")
async def roles_graph_edge(payload: Dict[str, Any] = Body(...)):
    a = str(payload.get("a") or "")
    b = str(payload.get("b") or "")
    w = float(payload.get("weight") or 1.0)
    ctx = str(payload.get("context") or "")
    if not a or not b or a == b:
        return JSONResponse({"ok": False, "error": "a and b must be different"}, status_code=400)
    touch_edge(a,b,w,ctx)
    return JSONResponse({"ok": True})

@router.get("/roles/graph/neighbors/{agent_id}")
async def roles_graph_neighbors(agent_id: str):
    return JSONResponse({"ok": True, "neighbors": neighbors(agent_id)})

@router.get("/roles/clarify/candidates")
async def roles_clarify_candidates():
    thr = float(os.getenv("ROLE_UNCERTAINTY_THR","0.35") or "0.35")
    people = list_people(limit=5000)
    out=[]
    for p in people:
        u = _uncertainty(p.get("vector") or {})
        if u >= thr:
            out.append({"agent_id": p["agent_id"], "uncertainty": round(u,3), "labels": p.get("labels",[])})
    out.sort(key=lambda x: x["uncertainty"], reverse=True)
    return JSONResponse({"ok": True, "threshold": thr, "candidates": out[:200]})

def mount_roles_graph(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app