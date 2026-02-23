# -*- coding: utf-8 -*-
"""
routes/window_watch_routes.py - upravlenie «zhivym pleybuferom».

Ruchki:
  POST /window/watch/start {"interval_ms":600}
  POST /window/watch/stop
  GET  /window/watch/status

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.ops.window_watch import start as ww_start, stop as ww_stop, status as ww_status
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("window_watch_routes", __name__, url_prefix="/window/watch")

@bp.route("/start", methods=["POST"])
def start():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(ww_start(int(data.get("interval_ms", 800))))

@bp.route("/stop", methods=["POST"])
def stop():
    return jsonify(ww_stop())

@bp.route("/status", methods=["GET"])
def status():
    return jsonify(ww_status())

def register(app):
    app.register_blueprint(bp)