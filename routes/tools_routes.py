# -*- coding: utf-8 -*-
"""routes.tools_routes

Minimal stub so register_all can import this module and attach a blueprint.

You can later replace this file with the real implementation.
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

tools_bp = Blueprint("tools_bp", __name__, url_prefix="/tools")


@tools_bp.get("/ping")
def ping():
    return jsonify({"ok": True, "module": "routes.tools_routes", "title": "Tools"})


def register(app):
    # Register only if not already present
    if tools_bp.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(tools_bp)
    return app