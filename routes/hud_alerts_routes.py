# -*- coding: utf-8 -*-
"""routes/hud_alerts_routes.py - REST/UI dlya HUD-alertov.

Ruchki:
  POST /hud_alerts/config {"p90_ms":800,"fail_rate":0.15,"allow_audio":true}
  POST /hud_alerts/enable {"enabled":true}
  POST /hud_alerts/build {"n":200}
  GET /hud_alerts/status
  GET /admin/hud_alerts

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict
from flask import Blueprint, jsonify, request, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Drop-in: sokhranyaem kontrakty moduley
try:
    from modules.instructor.hud_alerts import configure, enable, build, status  # type: ignore
except Exception:  # pragma: no cover
    configure = enable = build = status = None  # type: ignore

bp = Blueprint("hud_alerts_routes", __name__, url_prefix="/hud_alerts")


@bp.post("/config")
def cfg():
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    try:
        p90_ms = int(d.get("p90_ms", 800))
        fail_rate = float(d.get("fail_rate", 0.15))
        if not (0.0 <= fail_rate <= 1.0):
            raise ValueError("fail_rate out of range")
        allow_audio = bool(d.get("allow_audio", False))
    except (TypeError, ValueError) as e:
        return jsonify({"ok": False, "error": f"bad_input: {e}"}), 400

    if configure is None:
        return jsonify({"ok": False, "error": "hud_alerts unavailable"}), 500
    try:
        return jsonify(configure(p90_ms, fail_rate, allow_audio))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/enable")
def en():
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    enabled = bool(d.get("enabled", False))
    if enable is None:
        return jsonify({"ok": False, "error": "hud_alerts unavailable"}), 500
    try:
        return jsonify(enable(enabled))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/build")
def b():
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    try:
        n = int(d.get("n", 200))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "n must be integer"}), 400

    if build is None:
        return jsonify({"ok": False, "error": "hud_alerts unavailable"}), 500
    try:
        return jsonify(build(n))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/status")
def st():
    if status is None:
        return jsonify({"ok": False, "error": "hud_alerts unavailable"}), 500
    try:
        return jsonify(status())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/admin")
def admin():
    return render_template("admin_hud_alerts.html")


def register(app):  # pragma: no cover
    """Drop-in registration of blueprint (project contract)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


__all__ = ["bp", "register", "init_app"]