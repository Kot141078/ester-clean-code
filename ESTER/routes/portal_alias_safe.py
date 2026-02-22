from __future__ import annotations
import os
from datetime import datetime
from flask import Blueprint, current_app, jsonify, render_template, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BP_NAME = "portal_alias_safe"
bp = Blueprint(BP_NAME, __name__)

def _log(line: str) -> None:
    try:
        root = os.getenv("ESTER_DATA_ROOT", "data")
        os.makedirs(root, exist_ok=True)
        p = os.path.join(root, "bringup_after_chain.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.utcnow().isoformat()}] {line}\n")
    except Exception:
        pass  # don't break request flow

def _template_exists(name: str) -> bool:
    try:
        root = current_app.root_path  # project root
        path = os.path.join(root, "templates", name)
        return os.path.isfile(path)
    except Exception:
        return False

@bp.route("/_alias/portal/health", methods=["GET"])
def portal_health():
    data = {
        "ok": True,
        "source": BP_NAME,
        "ab": os.getenv("ESTER_PORTAL_ALIAS_SAFE_AB", "A"),
        "template_exists": _template_exists("portal.html"),
    }
    return jsonify(data), 200

@bp.route("/_alias/portal", methods=["GET"])
def portal_alias():
    if _template_exists("portal.html"):
        html = render_template("portal.html")
        return Response(html, 200, mimetype="text/html")
    html = """<!doctype html><html><head><meta charset="utf-8">
<title>Ester Portal (safe)</title></head>
<body style="font-family:system-ui,Segoe UI,Arial,sans-serif;padding:24px">
<h2>Ester Portal (safe alias)</h2>
<p>Shablon <code>templates/portal.html</code> ne nayden. Podlozhite ego — i stranitsa otkroetsya bez 500.</p>
</body></html>"""
    return Response(html, 200, mimetype="text/html")

def register(app):
    ab = os.getenv("ESTER_PORTAL_ALIAS_SAFE_AB", "A").upper()
    if ab != "B":
        _log(f"{BP_NAME}: AB={ab} -> skip")
        return False
    if BP_NAME not in app.blueprints:
        app.register_blueprint(bp)
    _log(f"{BP_NAME}: installed")
    return True