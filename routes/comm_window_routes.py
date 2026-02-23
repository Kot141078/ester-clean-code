# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, jsonify, request

from modules.runtime import comm_window
from modules.security.admin_guard import require_admin

bp_comm_window = Blueprint("comm_window_routes", __name__)


def _admin_guard():
    ok, reason = require_admin(request)
    if ok:
        return None
    return jsonify({"ok": False, "error": "forbidden", "reason": reason}), 403


@bp_comm_window.post("/debug/comm/open_window")
def debug_comm_open_window():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    allow_hosts = body.get("allow_hosts")
    if not isinstance(allow_hosts, list):
        allow_hosts = ["api.telegram.org"]
    rep = comm_window.open_window(
        kind=str(body.get("kind") or "telegram"),
        ttl_sec=int(body.get("ttl_sec") or 60),
        reason=str(body.get("reason") or ""),
        allow_hosts=allow_hosts,
    )
    code = 200 if rep.get("ok") else 400
    return jsonify(rep), code


@bp_comm_window.post("/debug/comm/close_window")
def debug_comm_close_window():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    rep = comm_window.close_window(str(body.get("window_id") or ""))
    code = 200 if rep.get("ok") else 404
    return jsonify(rep), code


@bp_comm_window.get("/debug/comm/list")
def debug_comm_list():
    denied = _admin_guard()
    if denied:
        return denied
    rep = comm_window.list_windows()
    return jsonify(rep), 200


def register(app):
    if bp_comm_window.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(bp_comm_window)
    return app

