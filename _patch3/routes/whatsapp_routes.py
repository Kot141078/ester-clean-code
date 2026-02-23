# -*- coding: utf-8 -*-
"""routes.whatsapp_routes

Minimal stub so register_all can import this module and attach a blueprint.

You can later replace this file with the real implementation.
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

whatsapp_bp = Blueprint("whatsapp_bp", __name__, url_prefix="/whatsapp")


@whatsapp_bp.get("/ping")
def ping():
    return jsonify({"ok": True, "module": "routes.whatsapp_routes", "title": "WhatsApp"})


def register(app):
    # Register only if not already present
    if whatsapp_bp.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(whatsapp_bp)
    return app