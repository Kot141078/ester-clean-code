# -*- coding: utf-8 -*-
"""
Simple JWT mint endpoints for local UI/debug flows.

Routes:
  GET  /auth/auto
  POST /auth/auto/api/issue
  POST /auth/ui/mint
  GET  /auth/auto/roles/me
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from flask import Blueprint, jsonify, render_template_string, request

try:
    from flask_jwt_extended import create_access_token, get_jwt, jwt_required
except Exception:  # pragma: no cover
    create_access_token = None  # type: ignore

    def jwt_required(*_a, **_kw):  # type: ignore
        def _wrap(fn):
            return fn

        return _wrap

    def get_jwt():  # type: ignore
        return {}


bp = Blueprint("auto_jwt", __name__, url_prefix="/auth/auto")
bp_ui = Blueprint("auth_ui", __name__, url_prefix="/auth/ui")


def _is_admin_name(user: str) -> bool:
    admins = [a.strip().lower() for a in str(os.getenv("ADMIN_USERNAMES", "owner,admin")).split(",") if a.strip()]
    return str(user or "").strip().lower() in admins


_HTML = """<!doctype html><meta charset="utf-8"/>
<title>Auto JWT</title>
<style>body{font:16px/1.4 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;padding:24px}</style>
<h1>Issue JWT</h1>
<p>Enter username. For configured admin names, role will be <code>admin</code>.</p>
<input id="user" placeholder="owner" value="owner"/>
<button id="go">Issue</button>
<pre id="out"></pre>
<script>
async function issue(){
  const user=document.getElementById('user').value||'user';
  const r=await fetch('/auth/auto/api/issue',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user})});
  const js=await r.json();
  if(js.ok){ try{ localStorage.setItem('jwt',js.token); }catch{} }
  document.getElementById('out').textContent=JSON.stringify(js,null,2);
}
document.getElementById('go').addEventListener('click',issue);
</script>
"""


@bp.get("")
def auto_ui():
    return render_template_string(_HTML)


@bp.post("/api/issue")
def api_issue():
    if not create_access_token:
        return jsonify({"ok": False, "error": "jwt_unavailable"}), 503
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    user = str(data.get("user") or "").strip() or "user"
    roles: List[str] = ["user"]
    if _is_admin_name(user):
        roles = ["admin", "user"]
    token = create_access_token(identity=user, additional_claims={"roles": roles, "user": user})
    return jsonify({"ok": True, "token": token, "user": user, "roles": roles})


@bp_ui.post("/mint")
def ui_mint():
    """Legacy-compatible mint endpoint: POST /auth/ui/mint {subject, role}."""
    if not create_access_token:
        return jsonify({"ok": False, "error": "jwt_unavailable"}), 503
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    subject = str(data.get("subject") or data.get("username") or "").strip() or "user"
    role = str(data.get("role") or "").strip().lower() or "user"
    roles = ["admin", "user"] if role == "admin" else ["user"]
    token = create_access_token(identity=subject, additional_claims={"roles": roles, "user": subject})
    return jsonify({"ok": True, "token": token, "user": subject, "roles": roles})


@bp.get("/roles/me")
@jwt_required()
def roles_me():
    return jsonify({"ok": True, "claims": get_jwt()})


def register(app):
    app.register_blueprint(bp)
    app.register_blueprint(bp_ui)
    return app
