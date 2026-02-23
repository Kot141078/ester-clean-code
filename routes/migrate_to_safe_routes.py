# -*- coding: utf-8 -*-
"""
routes/migrate_to_safe_routes.py - REST/UI migratsii stsenariev.

Ruchki:
  POST /migrate/preview {"steps":[...]} -> safe-predprosmotr
  POST /migrate/export  {"steps":[...]} -> finalnyy safe JSON
  GET  /admin/migrate

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.coop.migrate_to_safe import preview, export
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("migrate_to_safe_routes", __name__, url_prefix="/migrate")

@bp.route("/preview", methods=["POST"])
def prev():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(preview(list(data.get("steps") or [])))

@bp.route("/export", methods=["POST"])
def exp():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(export(list(data.get("steps") or [])))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_migrate.html")

def register(app):
    app.register_blueprint(bp)