# -*- coding: utf-8 -*-
"""routes/quality_guard_routes.py - REST/UI dlya politiki kachestva.

Ruchki:
  POST /quality/enable {"window_sec":60,"p90_ms":900,"error_rate":0.25,"hud_alerts":true}
  POST /quality/disable {}
  GET /quality/status
  POST /quality/ingest {"ok":true,"t_ms":120,"op":"hotkey"}
  POST /quality/check {} # ruchnoy progon periodic_check()
  GET /admin/quality

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.quality.guard import enable, disable, status as q_status, ingest, periodic_check
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("quality_guard_routes", __name__, url_prefix="/quality")

@bp.route("/enable", methods=["POST"])
def q_enable():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(enable(d))

@bp.route("/disable", methods=["POST"])
def q_disable():
    return jsonify(disable())

@bp.route("/status", methods=["GET"])
def q_status_():
    return jsonify(q_status())

@bp.route("/ingest", methods=["POST"])
def q_ingest():
    d = request.get_json(force=True, silent=True) or {}
    ingest(d)
    return jsonify({"ok": True})

@bp.route("/check", methods=["POST"])
def q_check():
    return jsonify(periodic_check())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_quality.html")

def register(app):
    app.register_blueprint(bp)