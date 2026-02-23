# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def register_proactive_feed_routes(app, memory_manager, url_prefix="/proactive"):
    bp = Blueprint("proactive_feed", __name__)

    def _load(user: str):
        try:
            meta = memory_manager.get_session_meta(user, "proactive_feed") or {}
            return list(meta.get("items") or [])
        except Exception:
            return []

    def _save(user: str, items):
        try:
            memory_manager.set_session_meta(user, "proactive_feed", {"items": items})
        except Exception:
            pass

    @bp.get(url_prefix + "/feed")
    @jwt_required()
    def feed_get():
        user = request.args.get("user", "Owner")
        items = _load(user)
        return jsonify({"items": items})

    @bp.post(url_prefix + "/feed/ack")
    @jwt_required()
    def feed_ack():
        data = request.get_json() or {}
        user = data.get("user", "Owner")
        ids = set(data.get("ids") or [])
        items = _load(user)
        if ids:
            items = [x for x in items if x.get("id") not in ids]
        else:
            items = []
        _save(user, items)
        return jsonify({"ok": True})

# app.register_blueprint(bp)