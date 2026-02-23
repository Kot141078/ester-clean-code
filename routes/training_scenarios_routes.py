# -*- coding: utf-8 -*-
"""
routes/training_scenarios_routes.py - REST/UI dlya «stsenariev obucheniya».

Ruchki:
  POST /training/start {"peers":[...],"mode":"iplay","steps":[...]}
  POST /training/stop  {}
  GET  /admin/training

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.coop.training_scenarios import start as tstart, stop as tstop
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("training_scenarios_routes", __name__, url_prefix="/training")

@bp.route("/start", methods=["POST"])
def start():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(tstart(data))

@bp.route("/stop", methods=["POST"])
def stop():
    return jsonify(tstop())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_training.html")

def register(app):
    app.register_blueprint(bp)