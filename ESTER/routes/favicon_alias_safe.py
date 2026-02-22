from __future__ import annotations
import os
from datetime import datetime
from flask import Blueprint, current_app, jsonify, send_file, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BP_NAME = "favicon_alias_safe"
bp = Blueprint(BP_NAME, __name__)

def _log(line: str) -> None:
    try:
        root = os.getenv("ESTER_DATA_ROOT", "data")
        os.makedirs(root, exist_ok=True)
        p = os.path.join(root, "bringup_after_chain.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.utcnow().isoformat()}] {line}\n")
    except Exception:
        pass

def _find_favicon() -> str | None:
    env_path = os.getenv("ESTER_FAVICON_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    root = current_app.root_path
    cand = os.path.join(root, "static", "favicon.ico")
    if os.path.isfile(cand):
        return cand
    cand = os.path.join(root, "favicon.ico")
    if os.path.isfile(cand):
        return cand
    return None

@bp.route("/_alias/favicon/ping", methods=["GET"])
def fav_ping():
    return jsonify({"ok": True, "source": BP_NAME}), 200

@bp.route("/_alias/favicon.ico", methods=["GET"])
def fav_icon():
    p = _find_favicon()
    if p:
        return send_file(p, mimetype="image/x-icon", as_attachment=False, download_name="favicon.ico")
    return Response("", 204)

def register(app):
    ab = os.getenv("ESTER_FAVICON_ALIAS_SAFE_AB", "A").upper()
    if ab != "B":
        _log(f"{BP_NAME}: AB={ab} -> skip")
        return False
    if BP_NAME not in app.blueprints:
        app.register_blueprint(bp)
    _log(f"{BP_NAME}: installed")
    return True