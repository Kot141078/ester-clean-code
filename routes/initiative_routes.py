# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, redirect, request

from modules.security.admin_guard import require_admin
from modules.runtime.status_iter18 import (
    run_initiatives_once,
    runtime_status,
    start_background_if_enabled,
)
from modules.volition.volition_gate import get_default_gate
try:
    from modules.agents import runtime as agents_runtime  # type: ignore
except Exception:  # pragma: no cover
    agents_runtime = None  # type: ignore

bp_initiatives = Blueprint("initiative_routes", __name__)


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "on", "y"}:
        return True
    if s in {"0", "false", "no", "off", "n"}:
        return False
    return bool(default)


def _admin_guard():
    ok, reason = require_admin(request)
    if ok:
        return None
    return jsonify({"ok": False, "error": "forbidden", "reason": reason}), 403


@bp_initiatives.get("/debug/initiatives/status")
def debug_initiatives_status():
    denied = _admin_guard()
    if denied:
        return denied
    st = runtime_status()
    return jsonify(
        {
            "ok": True,
            "memory_ready": st.get("memory_ready"),
            "degraded_memory_mode": st.get("degraded_memory_mode"),
            "initiatives": st.get("initiatives"),
            "background": st.get("background"),
        }
    )


@bp_initiatives.post("/debug/initiatives/run_once")
def debug_initiatives_run_once():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    dry = _as_bool(request.args.get("dry"), _as_bool(body.get("dry"), False))
    budgets = body.get("budgets") if isinstance(body.get("budgets"), dict) else None
    rep = run_initiatives_once(dry=dry, budgets=budgets)
    code = 200 if rep.get("ok") else 503
    return jsonify(rep), code


@bp_initiatives.get("/debug/agents/status")
def debug_agents_status():
    denied = _admin_guard()
    if denied:
        return denied
    if agents_runtime is None:
        return jsonify({"ok": False, "error": "agents_runtime_unavailable"}), 500
    return jsonify(agents_runtime.list_agents())


@bp_initiatives.post("/debug/agents/create")
def debug_agents_create():
    denied = _admin_guard()
    if denied:
        return denied
    if agents_runtime is None:
        return jsonify({"ok": False, "error": "agents_runtime_unavailable"}), 500
    body = request.get_json(silent=True) or {}
    template = str(body.get("template") or request.args.get("template") or "builder").strip() or "builder"
    dry = _as_bool(request.args.get("dry"), _as_bool(body.get("dry"), False))
    if dry:
        return jsonify({"ok": True, "dry_run": True, "template": template})
    rep = agents_runtime.create_agent(template, {"meta": {"source": "debug/agents/create"}})
    code = 200 if rep.get("ok") else 400
    return jsonify(rep), code


@bp_initiatives.post("/debug/agents/run_once")
def debug_agents_run_once():
    denied = _admin_guard()
    if denied:
        return denied
    if agents_runtime is None:
        return jsonify({"ok": False, "error": "agents_runtime_unavailable"}), 500
    body = request.get_json(silent=True) or {}
    agent_id = str(body.get("agent_id") or "").strip()
    if not agent_id:
        agent_id = agents_runtime.spawn_agent("procedural", "debug.agent", {"source": "debug/agents/run_once"})
    task = body.get("task")
    if not isinstance(task, dict):
        task = {
            "intent": "debug_agent_run_once",
            "action": "memory.add_note",
            "args": {
                "text": "debug agents run_once",
                "tags": ["debug", "agents"],
                "source": "debug.agents.route",
            },
            "needs": [],
        }
    budgets = body.get("budgets") if isinstance(body.get("budgets"), dict) else {}
    rep = agents_runtime.run_agent_once(agent_id, task, budgets, get_default_gate())
    code = 200 if rep.get("ok") else 503
    return jsonify(rep), code


@bp_initiatives.get("/initiatives")
def initiatives_page():
    user = str(request.args.get("user") or "default")
    mm = getattr(current_app, "memory_manager", None)
    items = []
    if mm is not None and hasattr(mm, "get_agenda"):
        try:
            raw = mm.get_agenda(user)  # type: ignore[attr-defined]
            if isinstance(raw, list):
                items = raw
        except Exception:
            items = []
    rows = []
    for it in items:
        oid = str(it.get("id") or "")
        title = str(it.get("title") or oid or "Initsiativa")
        rows.append(
            f"<li><b>{title}</b> "
            f"<a href='/initiatives/accept?id={oid}&user={user}'>Prinyat</a> "
            f"<a href='/initiatives/defer?id={oid}&min=60&user={user}'>Otlozhit</a></li>"
        )
    html = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>Initsiativy</title>"
        "<h1>Initsiativy</h1>"
        f"<p>Polzovatel: {user}</p>"
        "<ul>"
        + "".join(rows)
        + "</ul>"
    )
    return html


@bp_initiatives.get("/initiatives/accept")
def initiatives_accept():
    user = str(request.args.get("user") or "default")
    oid = str(request.args.get("id") or "")
    mm = getattr(current_app, "memory_manager", None)
    if mm is not None and hasattr(mm, "mark_offer"):
        try:
            mm.mark_offer(user, oid, "accepted")  # type: ignore[attr-defined]
        except Exception:
            pass
    return redirect(f"/initiatives?user={user}", code=302)


@bp_initiatives.get("/initiatives/defer")
def initiatives_defer():
    user = str(request.args.get("user") or "default")
    oid = str(request.args.get("id") or "")
    try:
        minutes = int(request.args.get("min") or "60")
    except Exception:
        minutes = 60
    mm = getattr(current_app, "memory_manager", None)
    if mm is not None and hasattr(mm, "snooze_offer"):
        try:
            mm.snooze_offer(user, oid, minutes)  # type: ignore[attr-defined]
        except Exception:
            pass
    return redirect(f"/initiatives?user={user}", code=302)


def register(app):
    if bp_initiatives.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(bp_initiatives)
    start_background_if_enabled()
    return app
