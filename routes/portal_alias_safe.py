# -*- coding: utf-8 -*-
"""
Safe portal alias:
- /_alias/portal         -> render templates/portal.html, or fallback HTML, NEVER 500
- /_alias/portal/health  -> JSON health
AB flag: ESTER_PORTAL_ALIAS_SAFE_AB (A|B), default: B (enabled)
"""
from __future__ import annotations
import os
from flask import Blueprint, current_app, jsonify, render_template, make_response
from datetime import datetime
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_bp = Blueprint("portal_alias_safe", __name__)

def _template_exists(name: str) -> bool:
    try:
        # Prefer real FS check (robust on Windows)
        root = getattr(current_app, "root_path", os.getcwd())
        path = os.path.join(root, "templates", name)
        return os.path.isfile(path)
    except Exception:
        return False

@_bp.get("/_alias/portal/health")
def _health():
    return jsonify(ok=True, src="portal_alias_safe", ts=datetime.utcnow().isoformat()+"Z")

@_bp.get("/_alias/portal")
def _portal():
    try:
        if _template_exists("portal.html"):
            # render user's real template
            html = render_template("portal.html")
            resp = make_response(html, 200)
            resp.headers["X-Ester-Alias"] = "portal_alias_safe"
            return resp
        else:
            # no template? - give minimal fallback (and a hint to /ui)
            html = """<!doctype html>
<html><head><meta charset="utf-8"><title>Ester Portal (fallback)</title></head>
<body style="font-family:system-ui,Segoe UI,Arial,sans-serif;margin:2rem">
<h1>Ester Portal</h1>
<p>Fayl <code>templates/portal.html</code> ne nayden. Otkryt <a href="/ui">/ui</a>.</p>
</body></html>"""
            resp = make_response(html, 200)
            resp.headers["X-Ester-Alias"] = "portal_alias_safe:fallback"
            return resp
    except Exception as e:
        # convert any internal error to safe HTML (but not 500)
        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Ester Portal (guard)</title></head>
<body style="font-family:system-ui,Segoe UI,Arial,sans-serif;margin:2rem">
<h1>Ester Portal</h1>
<p>Oshibka rendera portala perekhvachena guard'om.<br><small>{type(e).__name__}: {e}</small></p>
<p>Otkryt <a href="/ui">/ui</a>.</p>
</body></html>"""
        resp = make_response(html, 200)
        resp.headers["X-Ester-Guard"] = "portal_alias_safe"
        return resp

def register(app):
    ab = os.getenv("ESTER_PORTAL_ALIAS_SAFE_AB", "B").upper()
    if ab == "B":
        app.register_blueprint(_bp)