# -*- coding: utf-8 -*-
"""routes.admin_routes

Minimal stub so register_all can import this module and attach a blueprint.

You can later replace this file with the real implementation.
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")


@admin_bp.get("/ping")
def ping():
    return jsonify({"ok": True, "module": "routes.admin_routes", "title": "Admin"})


def register(app):
    # Register only if not already present
    if admin_bp.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(admin_bp)
    return app