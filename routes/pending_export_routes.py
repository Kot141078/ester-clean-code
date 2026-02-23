# -*- coding: utf-8 -*-
"""
routes/pending_export_routes.py - REST/UI eksportera pending_add.

Ruchki:
  POST /pending_export/normalize {"items":[...]}
  POST /pending_export/file      {"items":[...], "filename":"..."}
  GET  /admin/pending_export

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template, Response
from modules.triggers.pending_export import normalize, to_file
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("pending_export_routes", __name__, url_prefix="/pending_export")

@bp.route("/normalize", methods=["POST"])
def norm():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify({"ok": True, "items": normalize(list(d.get("items") or []))})

@bp.route("/file", methods=["POST"])
def file_():
    d = request.get_json(force=True, silent=True) or {}
    res = to_file(list(d.get("items") or []), str(d.get("filename","")))
    return Response(res["bytes"], mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename={res['filename']}"})

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_pending_export.html")

def register(app):
    app.register_blueprint(bp)