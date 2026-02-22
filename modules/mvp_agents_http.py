# modules/mvp_agents_http.py
from __future__ import annotations
from flask import Blueprint, jsonify, request

from modules.mvp_agents import list_profiles, run_agent
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mvp_agents", __name__)

@bp.get("/mvp/agents/health")
def health():
    return jsonify({"ok": True})

@bp.get("/mvp/agents/list")
def agents_list():
    return jsonify({"ok": True, "agents": list_profiles()})

@bp.post("/mvp/agents/run")
def agents_run():
    data = request.get_json(force=True, silent=True) or {}
    agent_id = str(data.get("id", "")).strip()
    payload = dict(data.get("payload") or {})
    res = run_agent(agent_id, payload)
    return jsonify(res), (200 if res.get("ok") else 400)

def register(app):
    # hook dlya autoload_everything
    if bp.name not in app.blueprints:
        app.register_blueprint(bp)
    return True