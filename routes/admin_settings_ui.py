# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, Iterable

from flask import Blueprint, jsonify, render_template, request

from modules.settings import store
from modules.settings.registry import (
    all_settings,
    get_setting,
    group_names,
    is_known_group,
    settings_for_group,
    validate_many,
)
from modules.state.audit_log import append_audit

try:
    from modules.auth.rbac import has_any_role
except Exception:  # pragma: no cover
    def has_any_role(_roles):  # type: ignore
        return False


bp = Blueprint("admin_settings_ui", __name__)
AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()


def _can_write() -> bool:
    return bool(has_any_role(["operator", "admin"]))


def _as_view(setting, current: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": setting.key,
        "group": setting.group,
        "type": setting.type,
        "default": setting.default,
        "value": current.get(setting.key, setting.default),
        "description": setting.description,
        "min": setting.min,
        "max": setting.max,
        "choices": list(setting.choices),
        "requires_restart": bool(setting.requires_restart),
        "is_sensitive": bool(setting.is_sensitive),
    }


def _collect_payload_keys(data: Dict[str, Any], allowed: Iterable[str]) -> Dict[str, Any]:
    allowed_set = set(allowed)
    values = data.get("values")
    if isinstance(values, dict):
        source = values
    else:
        source = data
    out: Dict[str, Any] = {}
    for key, value in source.items():
        if key in allowed_set:
            out[key] = value
    return out


@bp.get("/admin/settings")
def page_settings_index():
    groups = []
    current = store.load_all()
    for group in group_names():
        settings = settings_for_group(group)
        groups.append(
            {
                "name": group,
                "count": len(settings),
                "requires_restart": sum(1 for item in settings if item.requires_restart),
                "keys": [item.key for item in settings],
                "filled": sum(1 for item in settings if current.get(item.key) is not None),
            }
        )
    return render_template("admin_settings_index.html", groups=groups, ab_mode=AB_MODE)


@bp.get("/admin/settings/<group>")
def page_settings_group(group: str):
    if not is_known_group(group):
        return jsonify({"ok": False, "error": "unknown_group"}), 404

    current = store.load_all()
    items = [_as_view(item, current) for item in settings_for_group(group)]
    return render_template(
        "admin_settings_group.html",
        ab_mode=AB_MODE,
        group=group,
        settings=items,
    )


@bp.post("/admin/settings/<group>")
def api_settings_group(group: str):
    if not _can_write():
        return jsonify({"ok": False, "error": "rbac_forbidden"}), 403
    if not is_known_group(group):
        return jsonify({"ok": False, "error": "unknown_group"}), 404

    payload = request.get_json(silent=True) or {}
    allowed_keys = [item.key for item in settings_for_group(group)]
    incoming: Dict[str, Any] = _collect_payload_keys(payload, allowed_keys)

    unknown: Dict[str, str] = {}
    values = payload.get("values") if isinstance(payload.get("values"), dict) else payload
    for key in dict(values or {}).keys():
        if str(key) not in set(allowed_keys):
            unknown[str(key)] = "key_not_in_group"

    valid, errors = validate_many(incoming)
    if unknown:
        errors.update(unknown)
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    if AB_MODE != "B":
        append_audit("settings.group.save", {"mode": "dry", "dry": True, "group": group, "saved": len(valid)})
        return jsonify({"ok": True, "dry": True, "group": group, "saved": len(valid), "values": valid, "audit": "dry"})

    result = store.set_many(valid)
    if not bool(result.get("ok")):
        return jsonify(result), 400

    append_audit("settings.group.save", {"mode": "apply", "dry": False, "group": group, "saved": result.get("saved", 0)})
    return jsonify({"ok": True, "dry": False, "group": group, "saved": result.get("saved", 0), "values": valid})


@bp.get("/admin/settings/registry/json")
def api_settings_registry_json():
    rows = []
    current = store.load_all()
    for item in all_settings():
        rows.append(_as_view(item, current))
    return jsonify({"ok": True, "items": rows})


@bp.get("/admin/settings/value")
def api_settings_get_value():
    key = str(request.args.get("key", "") or "").strip()
    if not key or get_setting(key) is None:
        return jsonify({"ok": False, "error": "unknown_key"}), 404
    return jsonify({"ok": True, "key": key, "value": store.get(key)})


def register(app):  # pragma: no cover
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    register(app)

