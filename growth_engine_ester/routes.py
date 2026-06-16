# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, jsonify, request

from .config import status
from .decision_adapter import shadow_step
from .promotion_adapter import promote_candidate, rollback, verify_witness
from .replay_store import build_real_replay, replay_status
from .reports import build_report
from .signals import record_outcome
from .state import read_jsonl, state_paths

bp = Blueprint("srlm_routes", __name__)


def _admin_guard():
    try:
        from modules.security.admin_guard import require_admin  # type: ignore

        allowed, reason = require_admin(request)
        if allowed:
            return None
        return jsonify({"ok": False, "error": "forbidden", "reason": reason}), 403
    except Exception:
        roles = str(request.headers.get("X-User-Roles", "") or request.headers.get("X-Roles", "") or "")
        if "admin" in {part.strip().lower() for part in roles.split(",")}:
            return None
        return jsonify({"ok": False, "error": "forbidden", "reason": "admin_guard_unavailable"}), 403


@bp.get("/srlm/status")
def srlm_status():
    return jsonify(status())


@bp.get("/srlm/report")
def srlm_report():
    return jsonify(build_report())


@bp.get("/srlm/candidates")
def srlm_candidates():
    rows = read_jsonl(state_paths()["candidates"], limit=200)
    return jsonify({"ok": True, "candidates": rows})


@bp.get("/srlm/replay/status")
def srlm_replay_status():
    return jsonify(replay_status())


@bp.post("/srlm/replay/build")
def srlm_replay_build():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    try:
        min_n = int(body.get("min_n", 20) or 20)
    except Exception:
        min_n = 20
    rep = build_real_replay(min_n=min_n)
    return jsonify(rep), 200 if rep.get("ok") else 400


@bp.post("/srlm/record_outcome")
def srlm_record_outcome():
    denied = _admin_guard()
    if denied:
        return denied
    rep = record_outcome(request.get_json(silent=True) or {})
    return jsonify(rep), 200 if rep.get("ok") else 400


@bp.post("/srlm/shadow_step")
def srlm_shadow_step():
    denied = _admin_guard()
    if denied:
        return denied
    if not status().get("enabled"):
        return jsonify({"ok": False, "error_code": "SRLM_DISABLED", "error": "ESTER_SRLM_ENABLE is not enabled"}), 403
    rep = shadow_step(request.get_json(silent=True) or {})
    return jsonify(rep), 200 if rep.get("ok") else 400


@bp.post("/srlm/promote_candidate")
def srlm_promote_candidate():
    denied = _admin_guard()
    if denied:
        return denied
    rep = promote_candidate(request.get_json(silent=True) or {})
    return jsonify(rep), 200 if rep.get("ok") else 403


@bp.post("/srlm/rollback")
def srlm_rollback():
    denied = _admin_guard()
    if denied:
        return denied
    rep = rollback(request.get_json(silent=True) or {})
    return jsonify(rep), 200 if rep.get("ok") else 400


@bp.post("/srlm/verify_witness")
@bp.get("/srlm/verify_witness")
def srlm_verify_witness():
    return jsonify(verify_witness())


def register(app):
    app.register_blueprint(bp)
    return app
