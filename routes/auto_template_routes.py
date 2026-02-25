# -*- coding: utf-8 -*-
"""routes/auto_template_routes.py - REST/UI dlya avto-razmetki shablonov.

Ruchki:
  POST /auto_template/ingest {"samples":[...]}
  POST /auto_template/suggest {"win_w":120,"win_h":48,"threshold_base":0.82,"lang":"eng+rus"}
  GET /auto_template/export
  GET /admin/auto_template

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template

# Drop-in import: save paths and contracts as in a dump
from modules.vision.auto_template_labeler import ingest, suggest, export  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("auto_template_routes", __name__, url_prefix="/auto_template")


@bp.route("/ingest", methods=["POST"])
def i():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(ingest(list(d.get("samples") or [])))


@bp.route("/suggest", methods=["POST"])
def s():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(suggest(d))


@bp.route("/export", methods=["GET"])
def e():
    return jsonify(export())


@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_auto_template.html")


def register(app):  # pragma: no cover
    """Drop-in registration of blueprint (historical project contract)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


__all__ = ["bp", "register", "init_app"]