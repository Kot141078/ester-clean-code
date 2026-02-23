# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, jsonify, request

from modules.companion import companion_engine
from modules.security.admin_guard import require_admin

bp_companion = Blueprint("companion_routes", __name__)


def _admin_guard():
    ok, reason = require_admin(request)
    if ok:
        return None
    return jsonify({"ok": False, "error": "forbidden", "reason": reason}), 403


@bp_companion.post("/debug/companion/tick_once")
def debug_companion_tick_once():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    max_messages = int(body.get("max_messages") or 3)
    tail_n = int(body.get("tail_n") or 30)
    rep = companion_engine.tick_once(max_messages=max_messages, tail_n=tail_n)
    code = 200 if rep.get("ok") else 503
    return jsonify(rep), code


def register(app):
    if bp_companion.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(bp_companion)
    return app

