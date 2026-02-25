# -*- coding: utf-8 -*-
"""rutes/safe_windows_rutes.po - REST for safe windows.

Handles:
  POST /safe/network ZZF0Z
  GET /safe/status

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.security.safe_windows import set_policy, _load as _status
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("safe_windows_routes", __name__)

@bp.route("/safe/set", methods=["POST"])
def set_():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(set_policy(list(data.get("deny") or []), list(data.get("allow") or [])))

@bp.route("/safe/status", methods=["GET"])
def status():
    return jsonify({"ok": True, **_status()})

def register(app):
    app.register_blueprint(bp)