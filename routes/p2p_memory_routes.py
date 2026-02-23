# -*- coding: utf-8 -*-
"""
routes/p2p_memory_routes.py - REST for P2P memory synchronization.
"""
from __future__ import annotations

import logging
import os

from flask import Blueprint, jsonify, request

from modules.p2p import memory_sync


LOG = logging.getLogger("routes.p2p_memory_routes")
FEATURE_ENV = "ESTER_P2P_MEMORY_ENABLED"
_TRUE_SET = {"1", "true", "yes", "on", "y"}
P2P_SECRET = str(os.getenv("ESTER_P2P_MEMORY_SECRET", "") or "").strip()

bp = Blueprint("p2p_memory_routes", __name__, url_prefix="/p2p/memory")


def _env_enabled() -> bool:
    return str(os.getenv(FEATURE_ENV, "0") or "0").strip().lower() in _TRUE_SET


def _authorized(data: dict) -> bool:
    return str((data or {}).get("secret") or "") == P2P_SECRET


@bp.route("/status", methods=["GET"])
def status():
    idx = memory_sync.compute_index()
    return jsonify({"ok": True, **idx})


@bp.route("/pull_diff", methods=["POST"])
def pull_diff():
    d = request.get_json(force=True, silent=True) or {}
    if not _authorized(d):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    local_ids = list(memory_sync.store._MEM.keys())
    return jsonify({"ok": True, "missing": memory_sync.diff_index({"ids": local_ids})})


@bp.route("/import", methods=["POST"])
def import_():
    d = request.get_json(force=True, silent=True) or {}
    if not _authorized(d):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    return jsonify(memory_sync.import_records(d))


@bp.route("/push", methods=["POST"])
def push():
    d = request.get_json(force=True, silent=True) or {}
    if not _authorized(d):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    url = str(d.get("url") or "")
    secret = str(d.get("secret") or "")
    return jsonify(memory_sync.push(url, secret))


def register(app):
    if not _env_enabled():
        LOG.info("[p2p_memory_routes] disabled by env %s=0", FEATURE_ENV)
        return app
    if not P2P_SECRET:
        LOG.warning("[p2p_memory_routes] enabled but ESTER_P2P_MEMORY_SECRET is empty; skip register")
        return app
    if bp.name in getattr(app, "blueprints", {}):
        LOG.info("[p2p_memory_routes] blueprint already registered: %s", bp.name)
        return app
    app.register_blueprint(bp)
    LOG.info("[p2p_memory_routes] enabled and registered")
    return app

