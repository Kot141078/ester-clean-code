# -*- coding: utf-8 -*-
"""
routes/admin_ui_routes.py - legkie stranitsy adminki.

Mosty: (UI ↔ Operatsii), (RBAC ↔ Prozrachnost), (Audit ↔ Nadezhnost).
Zemnoy abzats: «Schitok s tumblerami» - otkryt panel i videt bazovye pokazateli.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:
    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn): return fn
        return _wrap

bp = Blueprint("admin_ui_routes", __name__)

@bp.get("/admin/ui")
@jwt_required(optional=True)
def admin_ui_index():
    try:
        return render_template("admin_index.html")
    except Exception:
        return jsonify({"ok": True, "ui": "admin_ui", "msg": "template missing"})

def register(app):
    if bp.name in getattr(app, "blueprints", {}):
        return app
    app.register_blueprint(bp)
    return app
