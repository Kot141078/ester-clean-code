# -*- coding: utf-8 -*-
"""routes/roles_clarify.py - metrika uverennosti profilya i “selektivnye voprosy” (+ optsionalnyy nudge).

MOSTY:
- (Yavnyy) /roles/uncertain/{agent_id} → confidence [0..1]; /roles/clarify → korotkiy vopros i (esli nado) postanovka nudzha.
- (Skrytyy #1) Questions generiruetsya evristicheski iz slabykh komponentov vektora (roles.store → profile.vector).
- (Skrytyy #2) Planning nudzha - pryamoy vyzov obrabotchika routes.nudges_routes.nudges_event, bez setevogo obkhoda.

ZEMNOY ABZATs:
Kogda Ester ne uverena, ona ne “dostaet” vsekh - tolko adresno i vezhlivo utochnyaet u konkretnogo cheloveka to, chto vazhno dlya zadachi.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, FastAPI, Body
from fastapi.responses import JSONResponse
import os, time

from roles.store import get_profile
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    from routes.nudges_routes import nudges_event  # optsionalno
except Exception:
    nudges_event = None  # type: ignore

TH = float(os.getenv("ROLE_CLARIFY_THRESHOLD","0.35") or "0.35")

router = APIRouter()

def _confidence(vec: Dict[str,float]) -> float:
    # simple metric: average level on key axes + “concentration”
    keys = ["experience","reaction","calm","coop","lead","comm","availability"]
    if not vec: return 0.0
    base = sum(float(vec.get(k,0.0)) for k in keys)/max(1,len(keys))
    spread = max(vec.values()) - min(vec.values())
    return max(0.0, min(1.0, 0.7*base + 0.3*(1.0 - spread)))

def _question_for(vec: Dict[str,float]) -> str:
    weak = sorted([(k,v) for k,v in vec.items()], key=lambda x:x[1])[:2]
    if not weak:
        return "How can you help now? Are there preferred tasks?"
    ask = []
    for k,_ in weak:
        if k == "availability":
            ask.append("When is it convenient for you to turn on in the next 24 hours?")
        elif k == "reaction":
            ask.append("How comfortable are you with urgent tasks?")
        elif k == "experience":
            ask.append("What tasks do you consider yourself confident in?")
        elif k == "comm":
            ask.append("How do you prefer to communicate (short/detailed)")
        else:
            ask.append(f"How do you approach tasks with an emphasis on “ZZF0Z”")
    return "Korotko utochnyu: " + "; ".join(ask) + "?"

@router.get("/roles/uncertain/{agent_id}")
async def roles_uncertain(agent_id: str):
    prof = get_profile(agent_id)
    if not prof:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    conf = _confidence(prof.get("vector") or {})
    return JSONResponse({"ok": True, "confidence": round(conf,4), "uncertain": conf < TH})

@router.post("/roles/clarify")
async def roles_clarify(payload: Dict[str, Any] = Body(...)):
    agent_id = str(payload.get("agent_id") or "")
    if not agent_id:
        return JSONResponse({"ok": False, "error": "agent_id required"}, status_code=400)
    prof = get_profile(agent_id)
    if not prof:
        return JSONResponse({"ok": False, "error": "profile not found"}, status_code=404)
    vec = prof.get("vector") or {}
    conf = _confidence(vec)
    q = _question_for(vec)
    sent = False
    if bool(payload.get("send_nudge")) and payload.get("channel_key") and nudges_event:
        # Let's create a local event for this actor
        ev = {
            "event_type":"AssignmentRequested",
            "entity_id":f"clarify:{agent_id}:{int(time.time())}",
            "ts":time.time(),
            "payload":{
                "actors":[{"agent_id":agent_id}],
                "summary":"profile clarification",
            }
        }
        # replace the intent through the field (using newges.engine intent_tpl)
        # in a simple form - the need will go away as a standard “accepted request”; the question text will be added to the intent and sent by the stylist
        try:
            await nudges_event(ev)  # type: ignore
            sent = True
        except Exception:
            sent = False
    return JSONResponse({"ok": True, "confidence": round(conf,4), "question": q, "nudge_scheduled": sent})

def mount_roles_clarify(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app