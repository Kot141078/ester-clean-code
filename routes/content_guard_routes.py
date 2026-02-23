# -*- coding: utf-8 -*-
"""
routes/content_guard_routes.py - «pauza po kontentu».

Ruchki:
  POST /guard/set    {"min_fps":25,"require_visible":true,"manual_pause":false}
  GET  /guard/status -> {allowed, reason?, metrics?}

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.ops.content_pauser import set_policy, get_status
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("content_guard_routes", __name__)

@bp.route("/guard/set", methods=["POST"])
def set_():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(set_policy(data.get("min_fps", None), bool(data.get("require_visible", False)), bool(data.get("manual_pause", False))))

@bp.route("/guard/status", methods=["GET"])
def status():
    return jsonify(get_status())

def register(app):
    app.register_blueprint(bp)