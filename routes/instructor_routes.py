# -*- coding: utf-8 -*-
"""
routes/instructor_routes.py - REST/UI dlya «rezhima instruktora».

Ruchki:
  POST /instructor/start {"peers":["192.168.1.22:8000"]}
  POST /instructor/stop  {}
  POST /instructor/ready {"peer":"192.168.1.22:8000"}
  POST /instructor/confirm {"peer":"ip:port","index":0,"ok":true,"latency_ms":250}
  GET  /instructor/status
  GET  /admin/instructor

# c=a+b
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Drop-in: sokhranyaem kontrakty moduley
try:
    from modules.coop.instructor_mode import start_class, stop_class, mark_ready, confirm, status  # type: ignore
except Exception:  # pragma: no cover
    start_class = stop_class = mark_ready = confirm = status = None  # type: ignore

bp = Blueprint("instructor_routes", __name__, url_prefix="/instructor")


@bp.route("/start", methods=["POST"])
def start():
    data = request.get_json(force=True, silent=True) or {}
    peers = list(data.get("peers") or [])
    if start_class is None:
        return jsonify({"ok": False, "error": "instructor module unavailable"}), 500
    try:
        return jsonify(start_class(peers))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/stop", methods=["POST"])
def stop():
    if stop_class is None:
        return jsonify({"ok": False, "error": "instructor module unavailable"}), 500
    try:
        return jsonify(stop_class())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/ready", methods=["POST"])
def ready():
    data = request.get_json(force=True, silent=True) or {}
    peer = data.get("peer", "unknown")
    if mark_ready is None:
        return jsonify({"ok": False, "error": "instructor module unavailable"}), 500
    try:
        return jsonify(mark_ready(peer))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/confirm", methods=["POST"])
def conf():
    data = request.get_json(force=True, silent=True) or {}
    try:
        peer = data.get("peer", "unknown")
        index = int(data.get("index", 0))
        ok = bool(data.get("ok", False))
        latency_ms = int(data.get("latency_ms", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "bad input"}), 400
    if confirm is None:
        return jsonify({"ok": False, "error": "instructor module unavailable"}), 500
    try:
        return jsonify(confirm(peer, index, ok, latency_ms))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/status", methods=["GET"])
def st():
    if status is None:
        return jsonify({"ok": False, "error": "instructor module unavailable"}), 500
    try:
        return jsonify(status())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_instructor.html")


def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


__all__ = ["bp", "register", "init_app"]