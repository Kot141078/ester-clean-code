# -*- coding: utf-8 -*-
"""
routes/gta_copilot_routes.py

REST endpoints for GTA V copilot bridge:
- POST /gta/ingest
- POST /gta/advice
- GET  /gta/status
- GET  /gta/last
- GET  /gta/ping
- GET  /gta/admin
"""
from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, render_template, request

from modules.gta import copilot

bp = Blueprint("gta_copilot_routes", __name__, url_prefix="/gta")


def _as_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v or "").strip().lower()
    if not s:
        return bool(default)
    return s in ("1", "true", "yes", "on", "y")


def _pick_sid(data: Dict[str, Any]) -> str:
    sid = (
        str(data.get("sid") or data.get("session_id") or data.get("chat_id") or os.getenv("GTA_COPILOT_SID", "gta-v"))
        .strip()
    )
    return sid or "gta-v"


@bp.get("/ping")
def ping():
    return jsonify({"ok": True, "module": "routes.gta_copilot_routes"})


@bp.get("/status")
def status():
    full = _as_bool(request.args.get("full"), False)
    return jsonify(copilot.status(full=full))


@bp.get("/last")
def last():
    return jsonify(
        {
            "ok": True,
            "state": copilot.get_last_state(),
            "advice": copilot.get_last_advice(),
        }
    )


@bp.post("/ingest")
def ingest():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    ask = _as_bool(data.get("ask"), False)
    force = _as_bool(data.get("force"), False)
    prompt = str(data.get("prompt") or data.get("user_prompt") or "").strip()
    sid = _pick_sid(data)
    user_id = str(data.get("user_id") or data.get("uid") or "gta-player").strip() or "gta-player"
    user_name = str(data.get("user_name") or data.get("user") or "Owner").strip() or "Owner"

    out = copilot.ingest(
        data,
        ask=ask,
        user_prompt=prompt,
        sid=sid,
        user_id=user_id,
        user_name=user_name,
        force=force,
    )
    return jsonify(out)


@bp.post("/advice")
def advice():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    force = _as_bool(data.get("force"), True)
    prompt = str(data.get("prompt") or data.get("user_prompt") or "").strip()
    sid = _pick_sid(data)
    user_id = str(data.get("user_id") or data.get("uid") or "gta-player").strip() or "gta-player"
    user_name = str(data.get("user_name") or data.get("user") or "Owner").strip() or "Owner"

    if isinstance(data.get("state"), dict):
        state_payload = data
    else:
        state_payload = {"state": copilot.get_last_state()}
    if not isinstance(state_payload.get("state"), dict) or not state_payload.get("state"):
        return jsonify({"ok": False, "error": "no_state"}), 400

    out = copilot.ingest(
        state_payload,
        ask=True,
        user_prompt=prompt,
        sid=sid,
        user_id=user_id,
        user_name=user_name,
        force=force,
    )
    return jsonify(out)


@bp.get("/admin")
def admin():
    return render_template("admin_gta_copilot.html")


def register(app):
    app.register_blueprint(bp)
