# -*- coding: utf-8 -*-
"""routes/roles_overrides.py - soft-overrides dlya orkestratora: personalnye bonusy i komandnaya affinnost.

MOSTY:
- (Yavnyy) POST /roles/overrides → {"overrides":[{agent_id,bias,why}], "team_bonus":x} - mozhno napryamuyu podmeshat v Orchestrator v2.
- (Skrytyy #1) Use rank_for_task(...) iz roles.store i team_affinity(...) bez izmeneniya /synergy/assign/v2.
- (Skrytyy #2) Format "why" prigoden dlya explainability v Synergy Board.

ZEMNOY ABZATs:
Pered naznacheniem roli sistema myagko “podtalkivaet” vybor - k tomu, kto podkhodit i u kogo uzhe slozhilas svyazka s komandoy.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, FastAPI, Body
from fastapi.responses import JSONResponse

from roles.store import rank_for_task
from roles.edges import team_affinity
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

@router.post("/roles/overrides")
async def roles_overrides(payload: Dict[str, Any] = Body(...)):
    task_text = str(payload.get("task_text") or "")
    dims = payload.get("dims") or {}
    candidates = [str(x) for x in (payload.get("candidates") or [])]
    top_n = int(payload.get("top_n") or max(1, len(candidates)))
    ranked = rank_for_task(task_text if task_text else None, dims, top_n=len(candidates) or 5)

    # normiruem v [0..1] i vydaem bias ~ +/-0.2
    if ranked:
        max_s = max(r["score"] for r in ranked) or 1.0
    else:
        max_s = 1.0
    biases=[]
    for r in ranked:
        if candidates and r["agent_id"] not in candidates:
            continue
        norm = (r["score"]/max_s)
        bias = round(0.2 * (norm - 0.5)*2.0, 4)  # -0.2..+0.2
        biases.append({
            "agent_id": r["agent_id"],
            "bias": bias,
            "why": [f"profile_match={r['score']:.2f} ({','.join(r.get('labels',[]))})"]
        })

    t_bonus = round(team_affinity(candidates), 4) if len(candidates) >= 2 else 0.0
    return JSONResponse({"ok": True, "overrides": biases[:top_n], "team_bonus": t_bonus})

def mount_roles_overrides(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app