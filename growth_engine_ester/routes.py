# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, jsonify, request

from .config import status
from .decision_adapter import shadow_step
from .outcome_candidates import accept_candidate, candidate_stats, list_candidates, propose_candidate, reject_candidate
from .promotion_adapter import promote_candidate, rollback, verify_witness
from .quality import list_outcomes, list_rejections, outcome_stats, replay_quality_profile
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


def _limit_offset():
    try:
        limit = int(request.args.get("limit", "50") or 50)
    except Exception:
        limit = 50
    try:
        offset = int(request.args.get("offset", "0") or 0)
    except Exception:
        offset = 0
    return max(1, min(200, limit)), max(0, offset)


@bp.get("/srlm/outcomes")
def srlm_outcomes():
    limit, offset = _limit_offset()
    return jsonify(list_outcomes(limit=limit, offset=offset))


@bp.get("/srlm/outcomes/stats")
def srlm_outcome_stats():
    return jsonify(outcome_stats())


@bp.get("/srlm/outcomes/rejections")
def srlm_outcome_rejections():
    limit, offset = _limit_offset()
    return jsonify(list_rejections(limit=limit, offset=offset))


@bp.get("/srlm/outcome_candidates")
def srlm_outcome_candidates():
    limit, offset = _limit_offset()
    status_filter = str(request.args.get("status", "") or "")
    return jsonify(list_candidates(limit=limit, offset=offset, status=status_filter))


@bp.get("/srlm/outcome_candidates/stats")
def srlm_outcome_candidate_stats():
    return jsonify(candidate_stats())


@bp.post("/srlm/outcome_candidates/propose")
def srlm_outcome_candidate_propose():
    denied = _admin_guard()
    if denied:
        return denied
    rep = propose_candidate(request.get_json(silent=True) or {})
    return jsonify(rep), 200 if rep.get("ok") else 400


@bp.post("/srlm/outcome_candidates/accept")
def srlm_outcome_candidate_accept():
    denied = _admin_guard()
    if denied:
        return denied
    rep = accept_candidate(request.get_json(silent=True) or {})
    return jsonify(rep), 200 if rep.get("ok") else 400


@bp.post("/srlm/outcome_candidates/reject")
def srlm_outcome_candidate_reject():
    denied = _admin_guard()
    if denied:
        return denied
    rep = reject_candidate(request.get_json(silent=True) or {})
    return jsonify(rep), 200 if rep.get("ok") else 400


@bp.get("/srlm/replay/quality")
def srlm_replay_quality():
    try:
        min_total = int(request.args.get("min_total", "20") or 20)
    except Exception:
        min_total = 20
    return jsonify(replay_quality_profile(min_total=min_total))


@bp.get("/srlm/replay/status")
def srlm_replay_status():
    try:
        min_n = int(request.args.get("min_n", "20") or 20)
    except Exception:
        min_n = 20
    return jsonify(replay_status(min_n=min_n))


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
