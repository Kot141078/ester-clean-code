# -*- coding: utf-8 -*-
"""
routes/ingest_control_ui.py - prostaya admin-stranitsa upravleniya inzhestom/indeksami/snapshotami.

Marshruty (Blueprint "ingest_admin"):
  GET  /admin/ingest       → HTML-panel
  GET  /admin/ingest/ping  → health (json)

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, Response, jsonify, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("ingest_admin", __name__)

@bp.get("/admin/ingest")
def admin_page():
    try:
        return render_template("ingest_admin.html")
    except Exception:
        return Response("<html><body><h3>Ingest Admin</h3></body></html>", mimetype="text/html")

@bp.get("/admin/ingest/ping")
def admin_ping():
    return jsonify({"ok": True, "service": "ingest_admin"})

def register_admin(app) -> None:
    if bp.name in getattr(app, "blueprints", {}):
        return
    app.register_blueprint(bp)

def register(app):
    # Fail-closed registration to avoid duplicate mount.
    if bp.name in getattr(app, "blueprints", {}):
        return app
    app.register_blueprint(bp)
    return app
