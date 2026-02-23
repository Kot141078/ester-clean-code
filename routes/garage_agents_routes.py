# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, jsonify, request

from modules.garage import agent_factory, agent_runner
from modules.runtime import oracle_requests, oracle_window
from modules.security.admin_guard import require_admin

bp_garage_agents = Blueprint("garage_agents_routes", __name__)


def _admin_guard():
    ok, reason = require_admin(request)
    if ok:
        return None
    return jsonify({"ok": False, "error": "forbidden", "reason": reason}), 403


@bp_garage_agents.get("/debug/garage/agents")
def debug_garage_agents_list():
    denied = _admin_guard()
    if denied:
        return denied
    rep = agent_factory.list_agents()
    rep["oracle_windows"] = oracle_window.list_windows()
    return jsonify(rep), 200


@bp_garage_agents.post("/debug/garage/agents/create")
def debug_garage_agents_create():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    spec = body.get("spec")
    if not isinstance(spec, dict):
        spec = {
            "name": str(body.get("name") or ""),
            "goal": str(body.get("goal") or ""),
            "allowed_actions": list(body.get("allowed_actions") or []),
            "budgets": dict(body.get("budgets") or {}),
            "owner": str(body.get("owner") or "debug"),
            "oracle_policy": dict(body.get("oracle_policy") or {}),
        }
    rep = agent_factory.create_agent(spec)
    code = 200 if rep.get("ok") else 400
    return jsonify(rep), code


@bp_garage_agents.post("/debug/garage/agents/run_once")
def debug_garage_agents_run_once():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    agent_id = str(body.get("agent_id") or "").strip()
    if not agent_id:
        return jsonify({"ok": False, "error": "agent_id_required"}), 400
    plan = body.get("plan")
    if not isinstance(plan, (dict, list, str)):
        return jsonify({"ok": False, "error": "plan_required"}), 400
    ctx = body.get("ctx")
    if not isinstance(ctx, dict):
        ctx = {}
    rep = agent_runner.run_once(agent_id, plan, ctx)
    code = 200 if rep.get("ok") else 503
    return jsonify(rep), code


@bp_garage_agents.post("/debug/oracle/open_window")
def debug_oracle_open_window():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    kind = str(body.get("kind") or "openai")
    ttl_sec = int(body.get("ttl_sec") or 60)
    reason = str(body.get("reason") or "")
    allow_hosts = body.get("allow_hosts")
    if not isinstance(allow_hosts, list):
        allow_hosts = ["api.openai.com"]
    rep = oracle_window.open_window(kind=kind, ttl_sec=ttl_sec, reason=reason, allow_hosts=allow_hosts)
    code = 200 if rep.get("ok") else 400
    return jsonify(rep), code


@bp_garage_agents.post("/debug/oracle/close_window")
def debug_oracle_close_window():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    window_id = str(body.get("window_id") or "").strip()
    rep = oracle_window.close_window(window_id)
    code = 200 if rep.get("ok") else 404
    return jsonify(rep), code


@bp_garage_agents.get("/debug/oracle/requests")
def debug_oracle_requests_list():
    denied = _admin_guard()
    if denied:
        return denied
    status = str(request.args.get("status") or "").strip() or None
    try:
        limit = int(request.args.get("limit") or 100)
    except Exception:
        limit = 100
    rep = oracle_requests.list_requests(status=status, limit=limit)
    code = 200 if rep.get("ok") else 400
    return jsonify(rep), code


@bp_garage_agents.post("/debug/oracle/requests/<request_id>/approve")
def debug_oracle_request_approve(request_id: str):
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    reason = str(body.get("reason") or "").strip()
    ttl_raw = body.get("ttl_sec")
    ttl_sec = None
    if ttl_raw is not None:
        try:
            ttl_sec = int(ttl_raw)
        except Exception:
            ttl_sec = None
    budgets = dict(body.get("budgets") or {})
    allow_agents = bool(body.get("allow_agents", True))
    rep = oracle_requests.approve_request(
        str(request_id or "").strip(),
        actor="ester:admin",
        reason=reason,
        ttl_sec=ttl_sec,
        budgets=budgets,
        allow_agents=allow_agents,
    )
    code = 200 if rep.get("ok") else 400
    return jsonify(rep), code


@bp_garage_agents.post("/debug/oracle/requests/<request_id>/deny")
def debug_oracle_request_deny(request_id: str):
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    reason = str(body.get("reason") or "denied_by_ester").strip()
    rep = oracle_requests.deny_request(
        str(request_id or "").strip(),
        actor="ester:admin",
        reason=reason,
    )
    code = 200 if rep.get("ok") else 400
    return jsonify(rep), code


def register(app):
    if bp_garage_agents.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(bp_garage_agents)
    return app
