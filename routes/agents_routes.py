# -*- coding: utf-8 -*-
"""routes/agents_routes.py - REST/UI dlya agentsov.

Ruchki:
  POST /agents/desktop/enqueue {"kind":"open_app","meta":{...}}
  POST /agents/installer/enqueue {"kind":"plan_install","meta":{...}}
  POST /agents/game/enqueue {"kind":"ttt_suggest","meta":{...}}
  POST /agents/dry_run {"agent":"desktop|installer|game","id":"..."}
  POST /agents/commit {"agent":"...","id":"..."}
  GET /agents/list {"agent":"..."}
  GET /admin/agents

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.agents.desktop_agent import DesktopAgent
from modules.agents.installer_agent import InstallerAgent
from modules.agents.game_mate_agent import GameMateAgent
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("agents_routes", __name__, url_prefix="/agents")

AGENTS = {
  "desktop": DesktopAgent(),
  "installer": InstallerAgent(),
  "game": GameMateAgent()
}

def _A(name:str):
    return AGENTS.get(name)

@bp.route("/<agent>/enqueue", methods=["POST"])
def enqueue(agent):
    d=request.get_json(force=True,silent=True) or {}
    A=_A(agent)
    if not A: return jsonify({"ok":False,"error":"unknown_agent"})
    return jsonify(A.enqueue(d.get("kind",""), d.get("meta") or {}))

@bp.route("/list", methods=["GET"])
def list_():
    agent=request.args.get("agent","desktop")
    A=_A(agent)
    if not A: return jsonify({"ok":False,"error":"unknown_agent"})
    return jsonify({"ok":True,"items":A.list()})

@bp.route("/dry_run", methods=["POST"])
def dry_run():
    d=request.get_json(force=True,silent=True) or {}
    A=_A(d.get("agent","desktop"))
    if not A: return jsonify({"ok":False,"error":"unknown_agent"})
    return jsonify(A.dry_run(d.get("id","")))

@bp.route("/commit", methods=["POST"])
def commit():
    d=request.get_json(force=True,silent=True) or {}
    A=_A(d.get("agent","desktop"))
    if not A: return jsonify({"ok":False,"error":"unknown_agent"})
    return jsonify(A.commit(d.get("id","")))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_agents.html")

def register(app):
    app.register_blueprint(bp)