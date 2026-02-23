# -*- coding: utf-8 -*-
"""
routes/macro_recorder_routes.py - REST/UI dlya makrorekordera.

Ruchki:
  POST /macro/arm       {}
  POST /macro/disarm    {}
  POST /macro/record    {"type":"hotkey|mouse_click|type_text", ...}
  GET  /macro/preview   {}
  GET  /macro/export    {}
  GET  /admin/macro

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.stream.macro_recorder import arm, disarm, record, preview, export_safe
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("macro_recorder_routes", __name__, url_prefix="/macro")

@bp.route("/arm", methods=["POST"])
def a():
    return jsonify(arm())

@bp.route("/disarm", methods=["POST"])
def d():
    return jsonify(disarm())

@bp.route("/record", methods=["POST"])
def r():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(record(data))

@bp.route("/preview", methods=["GET"])
def p():
    return jsonify(preview())

@bp.route("/export", methods=["GET"])
def e():
    return jsonify(export_safe())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_macro.html")

def register(app):
    app.register_blueprint(bp)