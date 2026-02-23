# -*- coding: utf-8 -*-
"""
routes/desktop_metrics_routes.py - REST dlya izmereniya FPS.

Ruchki:
  POST /desktop/metrics/fps/start {"target":"screen"|"window","window_id":123,"seconds":3}
  POST /desktop/metrics/fps/stop
  GET  /desktop/metrics/fps/status

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict

from modules.vision.fps_monitor import start as fps_start, stop as fps_stop, status as fps_status
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("desktop_metrics_routes", __name__, url_prefix="/desktop/metrics")

@bp.route("/fps/start", methods=["POST"])
def start():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    target = (data.get("target") or "screen").strip()
    wid = data.get("window_id")
    seconds = int(data.get("seconds") or 3)
    fps_start(target, wid, seconds)
    return jsonify({"ok": True})

@bp.route("/fps/stop", methods=["POST"])
def stop():
    fps_stop()
    return jsonify({"ok": True})

@bp.route("/fps/status", methods=["GET"])
def status():
    st = fps_status()
    return jsonify({"ok": True, **st})

def register(app):
    app.register_blueprint(bp)