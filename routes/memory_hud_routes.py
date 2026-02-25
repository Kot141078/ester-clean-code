# -*- coding: utf-8 -*-
"""routes/memory_hud_routes.py - REST dlya HUD-integratsii pamyati.

Ruchki:
  GET /memory/hud/check?q=...
  POST /memory/hud/remind {"goal":"..."}
  GET /memory/hud/status

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.hud_bridge import check_context, auto_remind
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("memory_hud_routes", __name__, url_prefix="/memory/hud")
_LAST: list[dict] = []

@bp.route("/check", methods=["GET"])
def check():
    q = request.args.get("q","")
    res = check_context(q)
    global _LAST; _LAST=res
    return jsonify({"ok":True,"query":q,"results":res})

@bp.route("/remind", methods=["POST"])
def remind():
    d = request.get_json(force=True,silent=True) or {}
    goal = d.get("goal","")
    auto_remind(goal)
    return jsonify({"ok":True,"goal":goal})

@bp.route("/status", methods=["GET"])
def status():
    return jsonify({"ok":True,"active":_LAST})

def register(app):
    app.register_blueprint(bp)