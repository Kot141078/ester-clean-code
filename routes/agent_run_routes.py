# -*- coding: utf-8 -*-
"""
routes/agent_run_routes.py - zapusk/stop ispolnitelya plana.

Ruchki:
  POST /agent/run   {"max_steps":200,"step_timeout_ms":4000}
  POST /agent/stop  {}
  GET  /agent/status
  GET  /admin/agent_run

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.act.runner import run as run_exec, stop as run_stop, status as run_status
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("agent_run_routes", __name__, url_prefix="/agent")

@bp.route("/run", methods=["POST"])
def run_():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(run_exec(int(d.get("max_steps",200)), int(d.get("step_timeout_ms",4000))))

@bp.route("/stop", methods=["POST"])
def stop_():
    return jsonify(run_stop())

@bp.route("/status", methods=["GET"])
def status_():
    return jsonify(run_status())

@bp.route("/admin_run", methods=["GET"])
def admin():
    return render_template("admin_agent_run.html")

def register(app):
    app.register_blueprint(bp)