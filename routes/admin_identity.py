# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, render_template, request

from modules.state.audit_log import append_audit
from modules.state.identity_store import load_anchor, load_profile, save_anchor, save_profile

try:
    from modules.auth.rbac import has_any_role
except Exception:  # pragma: no cover
    def has_any_role(_roles):  # type: ignore
        return False


bp = Blueprint("admin_identity", __name__)
AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()


def _can_write() -> bool:
    return bool(has_any_role(["operator", "admin"]))


@bp.get("/admin/identity")
def page_identity():
    return render_template(
        "admin_identity.html",
        ab_mode=AB_MODE,
        profile=load_profile(),
        anchor=load_anchor(),
    )


@bp.post("/admin/identity/profile")
def api_identity_profile():
    if not _can_write():
        return jsonify({"ok": False, "error": "rbac_forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    update: Dict[str, Any] = {
        "entity_name": payload.get("entity_name"),
        "human_name": payload.get("human_name"),
        "language": payload.get("language"),
        "timezone": payload.get("timezone"),
        "owner_aliases": payload.get("owner_aliases"),
        "owner_birth_date": payload.get("owner_birth_date"),
        "owner_personal_code": payload.get("owner_personal_code"),
        "owner_birth_place": payload.get("owner_birth_place"),
        "owner_citizenship": payload.get("owner_citizenship"),
        "owner_priority_statement": payload.get("owner_priority_statement"),
        "anchor_terms": payload.get("anchor_terms"),
    }

    if AB_MODE != "B":
        preview = load_profile()
        preview["entity_name"] = str(update.get("entity_name") or preview.get("entity_name") or "Ester").strip() or "Ester"
        preview["human_name"] = str(update.get("human_name") or preview["human_name"]).strip() or preview["human_name"]
        preview["language"] = str(update.get("language") or preview["language"]).strip() or preview["language"]
        preview["timezone"] = str(update.get("timezone") or preview["timezone"]).strip() or preview["timezone"]
        preview["owner_aliases"] = str(update.get("owner_aliases") or preview.get("owner_aliases") or "").strip()
        preview["owner_birth_date"] = str(update.get("owner_birth_date") or preview.get("owner_birth_date") or "").strip()
        preview["owner_personal_code"] = str(
            update.get("owner_personal_code") or preview.get("owner_personal_code") or ""
        ).strip()
        preview["owner_birth_place"] = str(update.get("owner_birth_place") or preview.get("owner_birth_place") or "").strip()
        preview["owner_citizenship"] = str(
            update.get("owner_citizenship") or preview.get("owner_citizenship") or ""
        ).strip()
        preview["owner_priority_statement"] = str(
            update.get("owner_priority_statement") or preview.get("owner_priority_statement") or ""
        ).strip()
        preview["anchor_terms"] = str(update.get("anchor_terms") or preview.get("anchor_terms") or "").strip()
        append_audit("identity.profile.save", {"mode": "dry", "dry": True})
        return jsonify({"ok": True, "dry": True, "profile": preview, "audit": "dry"})

    saved = save_profile(update)
    append_audit("identity.profile.save", {"mode": "apply", "dry": False})
    return jsonify({"ok": True, "dry": False, "profile": saved})


@bp.post("/admin/identity/anchor")
def api_identity_anchor():
    if not _can_write():
        return jsonify({"ok": False, "error": "rbac_forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    text = str(payload.get("anchor") or "")
    if not text.strip():
        return jsonify({"ok": False, "error": "anchor_required"}), 400

    if AB_MODE != "B":
        append_audit("identity.anchor.save", {"mode": "dry", "dry": True, "chars": len(text.strip())})
        return jsonify({"ok": True, "dry": True, "anchor": text.strip(), "audit": "dry"})

    saved = save_anchor(text)
    append_audit("identity.anchor.save", {"mode": "apply", "dry": False, "chars": len(saved)})
    return jsonify({"ok": True, "dry": False, "anchor": saved})


def register(app):  # pragma: no cover
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    register(app)
