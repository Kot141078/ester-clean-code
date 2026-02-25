# -*- coding: utf-8 -*-
"""routes/auto_calibrate_routes.py - REST/UI dlya avtokalibrovki.

Ruchki:
  POST /calibrate/quick {}
  POST /calibrate/manual {"px_per_cm":37.8}
  GET /calibrate/status
  GET /calibrate/admin - HTML
  GET /admin/calibrate - HTML (alias dlya sovmestimosti)

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template

# Drop-in import: kontrakty ne menyaem
from modules.desktop.auto_calibrate import quick_probe, set_manual, status  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("auto_calibrate_routes", __name__, url_prefix="/calibrate")


@bp.post("/quick")
def quick():
    try:
        return jsonify(quick_probe())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/manual")
def manual():
    data = request.get_json(silent=True) or {}
    px = data.get("px_per_cm", 37.8)
    try:
        px_val = float(px)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "px_per_cm must be a number"}), 400
    try:
        return jsonify(set_manual(px_val))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/status")
def status_route():
    try:
        return jsonify(status())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/admin")
def admin():
    return render_template("admin_calibrate.html")


# Alias pod /admin/calibrate (vne prefiksa blyuprinta) dobavim v register()
def _admin_calibrate_page():
    return render_template("admin_calibrate.html")


def register(app):
    """Drop-in registration of blueprint and alias /admin/calibrate."""
    app.register_blueprint(bp)
    # Adding a compatible admin page alias
    try:
        app.add_url_rule("/admin/calibrate", endpoint="admin_calibrate", view_func=_admin_calibrate_page, methods=["GET"])
    except Exception:
        # If the route already exists, silently ignore it
        pass


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


__all__ = ["bp", "register", "init_app"]