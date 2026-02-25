# -*- coding: utf-8 -*-
"""routes/undo_suggester_routes.py - REST/UI dlya avto-undo.

Ruchki:
  POST /undo/suggest {"steps":[...]} -> {suggested:[...]}
  POST /undo/patch {"steps":[...]} -> {patched:[...],steps:[...] }
  GET /admin/undo_suggest

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.coop.undo_suggester import suggest, patch
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("undo_suggester_routes", __name__, url_prefix="/undo")

@bp.route("/suggest", methods=["POST"])
def s():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(suggest(list(data.get("steps") or [])))

@bp.route("/patch", methods=["POST"])
def p():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(patch(list(data.get("steps") or [])))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_undo_suggest.html")

def register(app):
    app.register_blueprint(bp)