# -*- coding: utf-8 -*-
"""
routes/guide_export_routes.py - eksport tekuschego gayda.

Ruchki:
  POST /guide/export/current {"name":"guide_demo"} -> {zip, folder}
# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.export.guide_export import export_current
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("guide_export_routes", __name__, url_prefix="/guide/export")

@bp.route("/current", methods=["POST"])
def current():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "guide").strip()
    return jsonify(export_current(name))

def register(app):
    app.register_blueprint(bp)