# -*- coding: utf-8 -*-
"""
routes/synergy_assign_advisor.py - soft-sovetnik naznacheniy (bez lomki orkestratora).

MOSTY:
- (Yavnyy) POST /synergy/assign/advice → ranzhirovanie kandidatov pod zadachu + komandnyy bonus (affinnost).
- (Skrytyy #1) Ispolzuet roles.store.rank_for_task(...) i roles.edges.team_affinity(...) - chistyy add-on.
- (Skrytyy #2) Vozvraschaet explain 'why' (yarlyki/skory); udobno podsvetit v treyse bordy.

ZEMNOY ABZATs:
Ester predlagaet - operator reshaet. Sovety uchityvayut i «kto luchshe podkhodit», i «kto pritersya s komandoy».

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, FastAPI, Body
from fastapi.responses import JSONResponse

from roles.store import rank_for_task
from roles.edges import team_affinity
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

@router.post("/synergy/assign/advice")
async def synergy_assign_advice(payload: Dict[str, Any] = Body(...)):
    """
    Vkhod:
      - task_text (str) - opisanie zadachi (ili dims).
      - dims (dict[str,float]) - pozhelaniya po vektoram (optsionalno).
      - candidates (list[str]) - ogranichenie po agentam (optsionalno).
      - team (list[str]) - te, kto uzhe v sostave (optsionalno, dlya affinnosti).
      - top_n (int) - skolko sovetov vernut.
    """
    task_text = str(payload.get("task_text") or "")
    dims = payload.get("dims") or {}
    candidates = [str(x) for x in (payload.get("candidates") or [])]
    team = [str(x) for x in (payload.get("team") or [])]
    top_n = int(payload.get("top_n") or 5)

    ranked_all = rank_for_task(task_text if task_text else None, dims, top_n=1000)
    # filtruem po candidates pri neobkhodimosti
    ranked = [r for r in ranked_all if not candidates or r["agent_id"] in candidates]

    # normiruem i podgotovim explain
    adv=[]
    if ranked:
        max_s = max(r["score"] for r in ranked) or 1.0
        for r in ranked:
            norm = r["score"]/max_s
            adv.append({
                "agent_id": r["agent_id"],
                "score": round(r["score"],4),
                "normalized": round(norm,4),
                "labels": r.get("labels",[])[:3],
                "why": [f"profile_match={r['score']:.2f} ({','.join(r.get('labels',[]))})"]
            })
    team_bonus = team_affinity(team + [adv[0]["agent_id"]]) if (team and adv) else team_affinity(team) if team else 0.0
    adv.sort(key=lambda x:x["score"], reverse=True)
    return JSONResponse({"ok": True, "advice": adv[:max(1, top_n)], "team_bonus": round(team_bonus,4)})

def mount_assign_advisor(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app