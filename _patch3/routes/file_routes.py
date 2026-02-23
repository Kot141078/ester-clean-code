# -*- coding: utf-8 -*-
"""routes.file_routes

Minimal stub so register_all can import this module and attach a blueprint.

You can later replace this file with the real implementation.
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

file_bp = Blueprint("file_bp", __name__, url_prefix="/files")


@file_bp.get("/ping")
def ping():
    return jsonify({"ok": True, "module": "routes.file_routes", "title": "Files"})


def register(app):
    # Register only if not already present
    if file_bp.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(file_bp)
    return app