# -*- coding: utf-8 -*-
"""
routes/synergy_trace_overlay.py - REST: postroenie overleya (extras + overlay) dlya proizvolnogo plana.

MOSTY:
- (Yavnyy) POST /synergy/trace/overlay → {"extras":{advice,team_bonus,pairwise}, "overlay":{...}}.
- (Skrytyy #1) Kandidaty/komanda izvlekayutsya iz plana, esli ne peredany yavno.
- (Skrytyy #2) Ne izmenyaet resheniya orkestratora; potrebiteli sami reshat, kak otobrazhat overlay v UI.

ZEMNOY ABZATs:
Lyuboy plan mozhno «podsvetit»: gde profil sovpadaet s zadachey, gde lyudi priterty. Eto uskoryaet osoznannyy vybor.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, FastAPI, Body
from fastapi.responses import JSONResponse
import os

from modules.synergy.advisor import compute_advice
from modules.synergy.plan_overlay import build_overlay, _find_candidates_in_plan
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

@router.post("/synergy/trace/overlay")
async def synergy_trace_overlay(payload: Dict[str, Any] = Body(...)):
    plan = payload.get("plan") or {}
    task_text = str(payload.get("task_text") or "")
    dims = payload.get("dims") or {}
    candidates = [str(x) for x in (payload.get("candidates") or [])]
    team = [str(x) for x in (payload.get("team") or (plan.get("team") or []))]
    top_n = int(payload.get("top_n") or max(5, len(candidates) or 5))

    if not candidates:
        candidates = _find_candidates_in_plan(plan)

    extras = compute_advice(task_text, dims, candidates, team, top_n)
    overlay = build_overlay(plan, extras, alpha=None)
    return JSONResponse({"ok": True, "extras": extras, "overlay": overlay})

def mount_synergy_trace_overlay(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app