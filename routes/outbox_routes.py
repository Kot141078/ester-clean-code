# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, jsonify, request

from modules.companion import outbox
from modules.security.admin_guard import require_admin

bp_outbox = Blueprint("outbox_routes", __name__)


def _admin_guard():
    ok, reason = require_admin(request)
    if ok:
        return None
    return jsonify({"ok": False, "error": "forbidden", "reason": reason}), 403


@bp_outbox.get("/debug/outbox/tail")
def debug_outbox_tail():
    denied = _admin_guard()
    if denied:
        return denied
    try:
        n = int(request.args.get("n", "20") or "20")
    except Exception:
        n = 20
    rows = outbox.tail(max(1, n))
    return jsonify({"ok": True, "count": len(rows), "items": rows}), 200


@bp_outbox.post("/debug/outbox/enqueue")
def debug_outbox_enqueue():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    rep = outbox.enqueue(
        kind=str(body.get("kind") or "note"),
        text=str(body.get("text") or ""),
        meta=dict(body.get("meta") or {}),
        chain_id=str(body.get("chain_id") or ""),
        related_action=str(body.get("related_action") or ""),
    )
    code = 200 if rep.get("ok") else 400
    return jsonify(rep), code


@bp_outbox.post("/debug/outbox/mark_delivered")
def debug_outbox_mark_delivered():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    rep = outbox.mark_delivered(
        str(body.get("msg_id") or ""),
        str(body.get("channel") or ""),
        meta=dict(body.get("meta") or {}),
    )
    code = 200 if rep.get("ok") else 400
    return jsonify(rep), code


def register(app):
    if bp_outbox.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(bp_outbox)
    return app

