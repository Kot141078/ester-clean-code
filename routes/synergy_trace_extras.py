# -*- coding: utf-8 -*-
"""routes/synergy_trace_extras.py - REST dlya polucheniya "extras" (sovety+affinnost) k explain-trace orkestratsii.

MOSTY:
- (Yavnyy) POST /synergy/trace/extras → {"advice":[...], "team_bonus":x, "pairwise":{a__b:w}}
- (Skrytyy #1) Ne vmeshivaetsya v /synergy/assign/v2 - potrebiteli sami decide, kak podmeshivat extras v otobrazhenie/reshenie.
- (Skrytyy #2) Ispolzuet modules.synergy.advisor i obschie khranilischa roley/grafa, bez zavisimosti ot konkretnoy realizatsii orkestratora.

ZEMNOY ABZATs:
Mozhno ostavit orkestrator kak est - no pokazyvat operatoru “umnye” podskazki i realnuyu sygrannost komandy, povyshaya doverie i skorost resheniya.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, FastAPI, Body
from fastapi.responses import JSONResponse

from modules.synergy.advisor import compute_advice
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

@router.post("/synergy/trace/extras")
async def synergy_trace_extras(payload: Dict[str, Any] = Body(...)):
    task_text = str(payload.get("task_text") or "")
    dims = payload.get("dims") or {}
    candidates = [str(x) for x in (payload.get("candidates") or [])]
    team = [str(x) for x in (payload.get("team") or [])]
    top_n = int(payload.get("top_n") or 5)
    res = compute_advice(task_text, dims, candidates, team, top_n)
    return JSONResponse({"ok": True, **res})

def mount_synergy_trace_extras(app: FastAPI) -> None:
    app.include_router(router)
# c=a+b


def register(app):
    app.include_router(router)
    return app