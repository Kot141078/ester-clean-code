# -*- coding: utf-8 -*-
"""
routes/showtime_routes.py - REST/UI dlya pokaza gotovykh stsenariev ("showtime").

Ruchki:
  GET  /showtime/list
  POST /showtime/run {"name":"Notepad demo"}
  GET  /admin/showtime

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.showtime.presets import list_presets, run_preset
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("showtime_routes", __name__, url_prefix="/showtime")

@bp.route("/list", methods=["GET"])
def list_():
    return jsonify({"ok": True, "presets": list_presets()})

@bp.route("/run", methods=["POST"])
def run_():
    d = request.get_json(force=True, silent=True) or {}
    name = str(d.get("name") or "").strip()
    return jsonify(run_preset(name))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_showtime.html")

def register(app):
    app.register_blueprint(bp)