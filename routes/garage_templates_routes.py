# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, jsonify, request

from modules.garage.templates import create_agent_from_template, get_template, list_templates
from modules.security.admin_guard import require_admin

bp_garage_templates = Blueprint("garage_templates_routes", __name__)


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _admin_guard():
    ok, reason = require_admin(request)
    if ok:
        return None
    return jsonify({"ok": False, "error": "forbidden", "reason": reason}), 403


@bp_garage_templates.get("/debug/garage/templates")
def debug_garage_templates_list():
    denied = _admin_guard()
    if denied:
        return denied
    rows = list_templates()
    return jsonify({"ok": True, "count": len(rows), "templates": rows}), 200


@bp_garage_templates.get("/debug/garage/templates/<template_id>")
def debug_garage_templates_get(template_id: str):
    denied = _admin_guard()
    if denied:
        return denied
    tpl = get_template(template_id)
    if not tpl:
        return jsonify({"ok": False, "error": "template_not_found", "template_id": str(template_id or "")}), 404
    return jsonify({"ok": True, "template": tpl}), 200


@bp_garage_templates.post("/debug/garage/agents/create_from_template")
def debug_garage_agents_create_from_template():
    denied = _admin_guard()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    template_id = str(body.get("template_id") or "").strip()
    if not template_id:
        return jsonify({"ok": False, "error": "template_id_required"}), 400

    rep = create_agent_from_template(
        template_id=template_id,
        overrides={
            "name": str(body.get("name") or ""),
            "goal": str(body.get("goal") or ""),
            "owner": str(body.get("owner") or "ester"),
            "enable_oracle": _as_bool(body.get("enable_oracle", False)),
            "enable_comm": _as_bool(body.get("enable_comm", False)),
            "window_id": str(body.get("window_id") or ""),
        },
        dry_run=_as_bool(body.get("dry_run", False)),
    )
    if not rep.get("ok"):
        code = 404 if rep.get("error") == "template_not_found" else 400
        return jsonify(rep), code
    return jsonify(rep), 200


def register(app):
    if bp_garage_templates.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(bp_garage_templates)
    return app

