# -*- coding: utf-8 -*-
"""routes/safe_scenarios_routes.py - REST/UI dlya seyf-stsenariev.

Ruchki:
  POST /safe_scenarios/run {"steps":[...]}
  GET /safe_scenarios/status
  GET /admin/safe_scenarios

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.coop.safe_scenarios import run as srun, status as sstatus
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("safe_scenarios_routes", __name__, url_prefix="/safe_scenarios")

@bp.route("/run", methods=["POST"])
def run():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(srun(list(data.get("steps") or [])))

@bp.route("/status", methods=["GET"])
def status():
    return jsonify(sstatus())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_safe_scenarios.html")

def register(app):
    app.register_blueprint(bp)