# -*- coding: utf-8 -*-
"""
routes/proactive_routes.py - marshruty dlya proaktivnykh stsenariev (morning digest e2e).

# c=a+b
"""
from __future__ import annotations
import glob, os
from typing import Any, Dict, List
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:
    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn): return fn
        return _wrap

try:
    from proactive_notifier import MorningDigestDaemon  # type: ignore
except Exception:
    MorningDigestDaemon = None  # type: ignore

bp = Blueprint("proactive_routes", __name__, url_prefix="/proactive")


def _compat_result(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        out = dict(payload)
        out.setdefault("result", payload)
        return out
    return {"ok": True, "result": payload}


@bp.get("/morning/smoke")
@jwt_required(optional=True)
def morning_smoke():
    if MorningDigestDaemon is None:
        return jsonify({"ok": False, "error": "proactive_notifier missing"}), 500
    d = MorningDigestDaemon()
    res = d.smoke_tick()  # type: ignore[call-arg]
    return jsonify(_compat_result(res))

@bp.post("/morning/run")
@jwt_required(optional=True)
def morning_run():
    if MorningDigestDaemon is None:
        return jsonify({"ok": False, "error": "proactive_notifier missing"}), 500
    d = MorningDigestDaemon()
    args: Dict[str, Any] = request.get_json(True, True) or {}
    res = d.run_once(**args)  # type: ignore[call-arg]
    return jsonify(_compat_result(res))

@bp.get("/previews")
def previews():
    base = os.getenv("PERSIST_DIR") or os.path.join(os.getcwd(), "data")
    files = sorted(glob.glob(os.path.join(base, "previews", "*.json")))
    names = [os.path.basename(f) for f in files]
    return jsonify({"ok": True, "files": names, "items": names})

def register(app) -> None:
    if bp.name in getattr(app, "blueprints", {}):
        return
    app.register_blueprint(bp)
