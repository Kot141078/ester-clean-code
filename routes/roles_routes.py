# -*- coding: utf-8 -*-
"""
routes/roles_routes.py - pult roley leader/assistant/observer i forvarding.

Ruchki:
  GET  /roles/status
  POST /roles/set   {"role":"leader|assistant|observer"}
  POST /roles/add   {"host":"127.0.0.1:8000"}
  POST /roles/drop  {"host":"..."}
  POST /roles/forward {"tag":"missions.step","path":"/missions/step","payload":{...}} -> retranslyatsiya na peers

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict
from modules.thinking.role_router import status as st, set_role, add_peer, drop_peer, forward_call

from typing import Any, Dict, List
from fastapi import APIRouter, FastAPI, Body
from fastapi.responses import JSONResponse

from roles.ontology import get_ontology
from roles.store import list_people, get_profile, upsert_observation, apply_feedback, learn_batch, rank_for_task
from messaging.styler import render_for_keys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()
bp = Blueprint("roles_routes", __name__, url_prefix="/roles")

@bp.route("/status", methods=["GET"])
def status():
    return jsonify({"ok": True, **st()})

@bp.route("/set", methods=["POST"])
def set_():
    role = (request.get_json(force=True, silent=True) or {}).get("role","")
    return jsonify(set_role(role))

@bp.route("/add", methods=["POST"])
def add():
    host = (request.get_json(force=True, silent=True) or {}).get("host","")
    return jsonify(add_peer(host))

@bp.route("/drop", methods=["POST"])
def drop():
    host = (request.get_json(force=True, silent=True) or {}).get("host","")
    return jsonify(drop_peer(host))

@bp.route("/forward", methods=["POST"])
def forward():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(forward_call((data.get("tag") or ""), (data.get("path") or ""), (data.get("payload") or {})))

def register(app):
    app.register_blueprint(bp)
@router.get("/roles/ontology")
async def roles_ontology():
    return JSONResponse(get_ontology())

@router.get("/roles/people")
async def roles_people():
    return JSONResponse({"ok": True, "people": list_people()})

@router.get("/roles/{agent_id}")
async def roles_profile(agent_id: str):
    prof = get_profile(agent_id)
    if not prof:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    return JSONResponse({"ok": True, "profile": prof})

@router.post("/roles/observe")
async def roles_observe(payload: Dict[str, Any] = Body(...)):
    agent_id = str(payload.get("agent_id") or "")
    text = str(payload.get("text") or "")
    channel = str(payload.get("channel") or "unknown")
    meta = payload.get("meta") or {}
    if not agent_id or not text:
        return JSONResponse({"ok": False, "error": "agent_id and text required"}, status_code=400)
    prof = upsert_observation(agent_id, text, channel, meta)
    return JSONResponse({"ok": True, "profile": prof})

@router.post("/roles/feedback")
async def roles_feedback(payload: Dict[str, Any] = Body(...)):
    agent_id = str(payload.get("agent_id") or "")
    if not agent_id:
        return JSONResponse({"ok": False, "error": "agent_id required"}, status_code=400)
    add_labels = payload.get("add_labels") or []
    remove_labels = payload.get("remove_labels") or []
    delta = payload.get("delta") or {}
    note = payload.get("note") or ""
    prof = apply_feedback(agent_id, add_labels, remove_labels, delta, note)
    return JSONResponse({"ok": True, "profile": prof})

@router.post("/roles/learn")
async def roles_learn(payload: Dict[str, Any] = Body(default={})):
    window = int(payload.get("window_sec") or 7*24*3600)
    n = learn_batch(window_sec=window)
    return JSONResponse({"ok": True, "replayed": n})

@router.post("/roles/hints")
async def roles_hints(payload: Dict[str, Any] = Body(...)):
    task_text = str(payload.get("task_text") or "")
    dims = payload.get("dims") or {}
    top_n = int(payload.get("top_n") or 5)
    ranked = rank_for_task(task_text if task_text else None, dims, top_n)
    return JSONResponse({"ok": True, "ranked": ranked})

@router.post("/roles/style_preview")
async def roles_style_preview(payload: Dict[str, Any] = Body(...)):
    keys = payload.get("keys") or []
    intent = str(payload.get("intent") or "")
    kind = payload.get("kind")
    if not keys or not intent:
        return JSONResponse({"ok": False, "error": "keys and intent required"}, status_code=400)
    text = render_for_keys(keys, intent, adapt_kind=kind)
    return JSONResponse({"ok": True, "rendered_intent": text})

def mount_roles(app: FastAPI) -> None:
    app.include_router(router)
