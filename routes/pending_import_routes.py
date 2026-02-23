# -*- coding: utf-8 -*-
"""
routes/pending_import_routes.py - REST/UI master dobavleniya triggerov iz pending.

Ruchki:
  POST /pending_import/dry_run    {"items":[...], "batch":50}
  POST /pending_import/try_apply  {"items":[...], "batch":50}
  POST /pending_import/export     {"items":[...], "filename":"..."}
  GET  /admin/pending_import

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template, Response
from modules.triggers.pending_import import dry_run, try_apply, export_posts
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("pending_import_routes", __name__, url_prefix="/pending_import")

@bp.route("/dry_run", methods=["POST"])
def dr():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify(dry_run(list(d.get("items") or []), int(d.get("batch",50))))

@bp.route("/try_apply", methods=["POST"])
def ta():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify(try_apply(list(d.get("items") or []), int(d.get("batch",50))))

@bp.route("/export", methods=["POST"])
def ex():
    d=request.get_json(force=True, silent=True) or {}
    res=export_posts(list(d.get("items") or []), str(d.get("filename","")))
    return Response(res["bytes"], mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename={res['filename']}"})

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_pending_import.html")

def register(app):
    app.register_blueprint(bp)