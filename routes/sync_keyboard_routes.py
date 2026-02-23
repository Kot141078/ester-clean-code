# -*- coding: utf-8 -*-
"""
routes/sync_keyboard_routes.py - REST/UI for cooperative keyboard sync.
"""
from __future__ import annotations

import logging
import os

from flask import Blueprint, jsonify, render_template, request

from modules.coop.sync_keyboard import (
    enable,
    follower_ingest,
    leader_hotkey,
    leader_text,
    set_peers,
    status as st,
)
from modules.security.admin_guard import require_admin


LOG = logging.getLogger("routes.sync_keyboard_routes")
FEATURE_ENV = "ESTER_COOP_SYNC_ENABLED"
_TRUE_SET = {"1", "true", "yes", "on", "y"}

bp = Blueprint("sync_keyboard_routes", __name__, url_prefix="/sync/kbd")


def _env_enabled() -> bool:
    return str(os.getenv(FEATURE_ENV, "0") or "0").strip().lower() in _TRUE_SET


def _admin_guard():
    ok, reason = require_admin(request)
    if ok:
        return None
    return jsonify({"ok": False, "error": "forbidden", "reason": reason}), 403


@bp.before_request
def _guard_all():
    return _admin_guard()


@bp.route("/peers", methods=["POST"])
def peers():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(set_peers(list(data.get("peers") or [])))


@bp.route("/enable", methods=["POST"])
def en():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(enable(bool(data.get("enabled", False))))


@bp.route("/hotkey", methods=["POST"])
def hk():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(leader_hotkey(data.get("seq", "")))


@bp.route("/text", methods=["POST"])
def tx():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(leader_text(data.get("value", "")))


@bp.route("/ingest", methods=["POST"])
def ingest():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(follower_ingest(data))


@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_kbd.html")


def register(app):
    if not _env_enabled():
        LOG.info("[sync_keyboard_routes] disabled by env %s=0", FEATURE_ENV)
        return app
    if bp.name in getattr(app, "blueprints", {}):
        LOG.info("[sync_keyboard_routes] blueprint already registered: %s", bp.name)
        return app
    app.register_blueprint(bp)
    LOG.info("[sync_keyboard_routes] enabled and registered")
    return app

