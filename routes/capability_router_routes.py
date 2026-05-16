# -*- coding: utf-8 -*-
"""HTTP status for the public-safe multimodal capability router."""

from __future__ import annotations

from flask import Blueprint, jsonify

from modules.capabilities.router import route_for, status


bp = Blueprint("capability_router_routes", __name__)


@bp.get("/capabilities/router")
@bp.get("/capabilities/router/status")
def api_capability_router_status():
    return jsonify(status())


@bp.get("/capabilities/router/<kind>")
def api_capability_route(kind: str):
    return jsonify({"ok": True, "route": route_for(kind)})


def register(app):
    app.register_blueprint(bp)
    return app
