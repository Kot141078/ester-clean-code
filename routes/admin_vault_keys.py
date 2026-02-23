# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, redirect, render_template, request

from modules.security.vault_store import SUPPORTED_PROVIDERS, list_status, set_secret, unset_secret, vault_status
from modules.state.audit_log import append_audit

try:
    from modules.auth.rbac import has_any_role
except Exception:  # pragma: no cover
    def has_any_role(_roles):  # type: ignore
        return False


bp = Blueprint("admin_vault_keys", __name__)
AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()


def _can_write() -> bool:
    return bool(has_any_role(["operator", "admin"]))


@bp.get("/admin/keys_vault")
def page_vault_alias():
    return redirect("/admin/keys/vault", code=302)


@bp.get("/admin/keys/vault")
def page_vault():
    return render_template(
        "admin_keys_vault.html",
        ab_mode=AB_MODE,
        providers=list(SUPPORTED_PROVIDERS),
        vault=vault_status(),
        status=list_status(SUPPORTED_PROVIDERS),
    )


@bp.get("/admin/keys/vault/status")
def api_vault_status():
    rows = list_status(SUPPORTED_PROVIDERS)
    return jsonify(rows)


@bp.post("/admin/keys/vault/set")
def api_vault_set():
    if not _can_write():
        return jsonify({"ok": False, "error": "rbac_forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    provider = str(payload.get("provider") or "").strip().upper()
    value = str(payload.get("value") or "")
    if provider not in SUPPORTED_PROVIDERS:
        return jsonify({"ok": False, "error": "provider_not_supported"}), 400
    if not value.strip():
        return jsonify({"ok": False, "error": "secret_required"}), 400

    if AB_MODE != "B":
        append_audit("vault.secret.set", {"mode": "dry", "dry": True, "provider": provider})
        return jsonify({"ok": True, "dry": True, "provider": provider, "set": True, "audit": "dry"})

    result: Dict[str, Any] = set_secret(provider, value)
    if not bool(result.get("ok")):
        code = 400 if result.get("error") == "dpapi_unavailable" else 500
        return jsonify(result), code

    append_audit("vault.secret.set", {"mode": "apply", "dry": False, "provider": provider})
    return jsonify(result)


@bp.post("/admin/keys/vault/unset")
def api_vault_unset():
    if not _can_write():
        return jsonify({"ok": False, "error": "rbac_forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    provider = str(payload.get("provider") or "").strip().upper()
    if provider not in SUPPORTED_PROVIDERS:
        return jsonify({"ok": False, "error": "provider_not_supported"}), 400

    if AB_MODE != "B":
        append_audit("vault.secret.unset", {"mode": "dry", "dry": True, "provider": provider})
        return jsonify({"ok": True, "dry": True, "provider": provider, "set": False, "audit": "dry"})

    result = unset_secret(provider)
    if not bool(result.get("ok")):
        code = 400 if result.get("error") == "dpapi_unavailable" else 500
        return jsonify(result), code
    append_audit("vault.secret.unset", {"mode": "apply", "dry": False, "provider": provider})
    return jsonify(result)


def register(app):  # pragma: no cover
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    register(app)

