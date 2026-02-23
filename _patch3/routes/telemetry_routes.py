# -*- coding: utf-8 -*-
"""routes.telemetry_routes

Minimal stub so register_all can import this module and attach a blueprint.

You can later replace this file with the real implementation.
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

telemetry_bp = Blueprint("telemetry_bp", __name__, url_prefix="/telemetry")


@telemetry_bp.get("/ping")
def ping():
    return jsonify({"ok": True, "module": "routes.telemetry_routes", "title": "Telemetry"})


def register(app):
    # Register only if not already present
    if telemetry_bp.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(telemetry_bp)
    return app