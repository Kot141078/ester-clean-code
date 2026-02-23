# -*- coding: utf-8 -*-
"""
Safe favicon alias:
- /_alias/favicon.ico  -> returns icon if found, else 204
- /_alias/favicon/ping -> 200 JSON with has_icon
AB flag: ESTER_FAVICON_ALIAS_SAFE_AB (A|B), default: B (enabled)
"""
from __future__ import annotations
import os
from flask import Blueprint, current_app, jsonify, send_file, make_response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_bp = Blueprint("favicon_alias_safe", __name__)

def _find_icon_path() -> str | None:
    # 1) explicit path via ENV
    env_path = os.getenv("ESTER_FAVICON_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    # 2) project static/favicon.ico
    root = getattr(current_app, "root_path", os.getcwd())
    static_ico = os.path.join(root, "static", "favicon.ico")
    if os.path.isfile(static_ico):
        return static_ico
    # 3) templates/favicon.ico (rare but try)
    tmpl_ico = os.path.join(root, "templates", "favicon.ico")
    if os.path.isfile(tmpl_ico):
        return tmpl_ico
    return None

@_bp.get("/_alias/favicon/ping")
def _ping():
    path = _find_icon_path()
    return jsonify(ok=True, src="favicon_alias_safe", has_icon=bool(path))

@_bp.get("/_alias/favicon.ico")
def _favicon():
    path = _find_icon_path()
    if path:
        resp = send_file(path, mimetype="image/x-icon", as_attachment=False, max_age=3600)
        resp.headers["X-Ester-Alias"] = "favicon_alias_safe"
        return resp
    # no icon → 204
    resp = make_response("", 204)
    resp.headers["X-Ester-Alias"] = "favicon_alias_safe"
    return resp

def register(app):
    ab = os.getenv("ESTER_FAVICON_ALIAS_SAFE_AB", "B").upper()
    if ab == "B":
        app.register_blueprint(_bp)