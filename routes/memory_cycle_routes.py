# -*- coding: utf-8 -*-
"""
routes/memory_cycle_routes.py - REST/UI dlya sutochnogo tsikla pamyati.

Ruchki:
  GET  /memory/cycle/status
  POST /memory/cycle/run_now
  POST /memory/cycle/scheduler_start
  POST /memory/cycle/scheduler_stop
  GET  /admin/memory_cycle

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, render_template
from modules.memory import daily_cycle
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("memory_cycle_routes", __name__, url_prefix="/memory/cycle")

@bp.route("/status", methods=["GET"])
def status():
    return jsonify(daily_cycle.status())

@bp.route("/run_now", methods=["POST"])
def run_now():
    return jsonify(daily_cycle.run_cycle(manual=True))

@bp.route("/scheduler_start", methods=["POST"])
def scheduler_start():
    return jsonify(daily_cycle.start_scheduler())

@bp.route("/scheduler_stop", methods=["POST"])
def scheduler_stop():
    return jsonify(daily_cycle.stop_scheduler())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_memory_cycle.html")

def register(app):
    app.register_blueprint(bp)