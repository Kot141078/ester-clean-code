
# -*- coding: utf-8 -*-
"""routes/agent_routes.py - REST-ruchki planirovaniya agenta (bez vypolneniya).

Ruchki:
  POST /agent/step {"goal":"otkryt bloknot i sokhranit fayl"}
  GET /agent/queue
  POST /agent/clear {}
  GET /admin/agent_plan

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.thinking.loop import step as think_step
from modules.planner.forge import queue as get_queue, clear as clear_queue
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("agent_routes", __name__, url_prefix="/agent")

@bp.route("/step", methods=["POST"])
def step():
    d = request.get_json(force=True, silent=True) or {}
    goal = str(d.get("goal","")).strip()
    return jsonify(think_step(goal))

@bp.route("/queue", methods=["GET"])
def q():
    return jsonify({"ok": True, "queue": get_queue()})

@bp.route("/clear", methods=["POST"])
def c():
    clear_queue()
    return jsonify({"ok": True})

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_agent_plan.html")

def register(app):
    app.register_blueprint(bp)