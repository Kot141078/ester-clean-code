# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, jsonify, request

from modules.agents import governed_mesh
from modules.security.admin_guard import require_admin

bp = Blueprint("useful_agent_mesh_routes", __name__)


def _admin_guard():
    ok, reason = require_admin(request)
    if ok:
        return None
    return jsonify({"ok": False, "error": "forbidden", "reason": reason}), 403


@bp.get("/agents/useful_mesh/status")
@bp.get("/debug/agents/useful_mesh/status")
def useful_mesh_status():
    return jsonify(governed_mesh.status())


@bp.post("/debug/agents/useful_mesh/reconcile")
def useful_mesh_reconcile():
    denied = _admin_guard()
    if denied:
        return denied
    rep = governed_mesh.reconcile(create_missing=True)
    return jsonify(rep), 200 if rep.get("ok") else 400


@bp.post("/debug/agents/useful_mesh/maintain")
def useful_mesh_maintain():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    force = bool(body.get("force_enqueue", False))
    rep = governed_mesh.maintain(enqueue_due=True, force_enqueue=force)
    return jsonify(rep), 200 if rep.get("ok") else 400


def register(app):
    app.register_blueprint(bp)
    return app
