# -*- coding: utf-8 -*-
"""routes.chat_api_routes

Minimal stub so register_all can import this module and attach a blueprint.

You can later replace this file with the real implementation.
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

chat_api_bp = Blueprint("chat_api_bp", __name__, url_prefix="/api")


@chat_api_bp.get("/ping")
def ping():
    return jsonify({"ok": True, "module": "routes.chat_api_routes", "title": "Chat API"})


def register(app):
    # Register only if not already present
    if chat_api_bp.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(chat_api_bp)
    return app