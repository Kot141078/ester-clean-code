# -*- coding: utf-8 -*-
"""routes/consent_gate_routes.py - REST/UI dlya "shlyuza soglasiya".

Ruchki:
  POST /consent/grant {"scope":"full_control","ttl_sec":900}
  POST /consent/check {"scope":"full_control"}
  POST /consent/revoke {"scope":"full_control"}
  GET /consent/status
  GET /admin/consent (alias vne prefiksa blyuprinta)
  GET /consent/admin (stranitsa v ramkakh blyuprinta)

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template

# Drop-in import: sokhranyaem kontrakt moduley
from modules.security.consent_gate import grant, check, revoke, status  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("consent_gate_routes", __name__, url_prefix="/consent")


@bp.post("/grant")
def api_grant():
    data = request.get_json(force=True, silent=True) or {}
    scope = str(data.get("scope", "full_control"))
    ttl_raw = data.get("ttl_sec", 900)
    try:
        ttl_sec = int(ttl_raw)
        if ttl_sec <= 0:
            raise ValueError
    except Exception:
        return jsonify({"ok": False, "error": "ttl_sec must be positive integer"}), 400

    try:
        return jsonify(grant(scope, ttl_sec))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/check")
def api_check():
    data = request.get_json(force=True, silent=True) or {}
    scope = str(data.get("scope", "full_control"))
    try:
        return jsonify(check(scope))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/revoke")
def api_revoke():
    data = request.get_json(force=True, silent=True) or {}
    scope = str(data.get("scope", "full_control"))
    try:
        return jsonify(revoke(scope))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/status")
def api_status():
    try:
        return jsonify(status())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/admin")
def admin():
    return render_template("admin_consent.html")


# Alias pod /admin/consent (vne prefiksa blyuprinta) dobavim v register()
def _admin_consent_page():
    return render_template("admin_consent.html")


def register(app):  # pragma: no cover
    """Drop-in registration of blueprint and alias /admin/consent."""
    app.register_blueprint(bp)
    # Adding a compatible admin page alias
    try:
        app.add_url_rule("/admin/consent", endpoint="admin_consent", view_func=_admin_consent_page, methods=["GET"])
    except Exception:
        # If the route already exists, silently ignore it
        pass


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


__all__ = ["bp", "register", "init_app"]