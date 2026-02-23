# -*- coding: utf-8 -*-
"""routes.mission_routes

Minimal stub so register_all can import this module and attach a blueprint.

You can later replace this file with the real implementation.
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

mission_bp = Blueprint("mission_bp", __name__, url_prefix="/mission")


@mission_bp.get("/ping")
def ping():
    return jsonify({"ok": True, "module": "routes.mission_routes", "title": "Mission"})


def register(app):
    # Register only if not already present
    if mission_bp.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(mission_bp)
    return app