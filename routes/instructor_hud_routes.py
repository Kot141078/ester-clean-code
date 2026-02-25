# -*- coding: utf-8 -*-
"""
routes/instructor_hud_routes.py - REST/UI HUD instruktora.

Ruchki:
  POST /instructor_hud/enable {"enabled":true}
  POST /instructor_hud/build  {"n":200}
  GET  /instructor_hud/status
  GET  /admin/instructor_hud

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict
from flask import Blueprint, jsonify, request, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Drop-in: sokhranyaem kontrakty moduley
try:
    from modules.instructor.hud import enable, build, status  # type: ignore
except Exception:  # pragma: no cover
    enable = build = status = None  # type: ignore

bp = Blueprint("instructor_hud_routes", __name__, url_prefix="/instructor_hud")


@bp.route("/enable", methods=["POST"])
def en():
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    if enable is None:
        return jsonify({"ok": False, "error": "instructor_hud unavailable"}), 500
    try:
        enabled = bool(d.get("enabled", False))
        return jsonify(enable(enabled))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/build", methods=["POST"])
def b():
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    if build is None:
        return jsonify({"ok": False, "error": "instructor_hud unavailable"}), 500
    try:
        n = int(d.get("n", 200))
        return jsonify(build(n))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "n must be integer"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/status", methods=["GET"])
def st():
    if status is None:
        return jsonify({"ok": False, "error": "instructor_hud unavailable"}), 500
    try:
        return jsonify(status())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_instructor_hud.html")


def register(app):  # pragma: no cover
    """Drop-in registration of blueprint (project contract)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


__all__ = ["bp", "register", "init_app"]