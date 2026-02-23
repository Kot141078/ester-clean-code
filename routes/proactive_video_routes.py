# -*- coding: utf-8 -*-
"""
routes/proactive_video_routes.py — REST-panel proaktivnogo videoobkhoda:
  POST /proactive/video/run  {mode:"subs"|"search", topic?, limit?}
  GET  /proactive/video/state

Mosty:
- Yavnyy: (UX v†" Proaktiv) HTTP-knopka dlya ruchnogo zapuska Re integratsii s suschestvuyuschim planirovschikom Ester.
- Skrytyy #1: (Kibernetika v†" Bezopasnost) Zapusk tolko po yavnomu vyzovu; avtozapusk upravlyaetsya ENV/kron.
- Skrytyy #2: (Infoteoriya v†" Memory) R ezultaty marshrutiziruyutsya cherez ingest yadro, bez lomki kontraktov.

Zemnoy abzats:
Eto "knopka obkhoda sklada": nazhal — master probezhal, otdal na liniyu vse novoe, vernul otchet.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.proactive.video_autorunner import run_once, state  # type: ignore
except Exception:
    run_once = None  # type: ignore
    state = None  # type: ignore

bp_proactive_video = Blueprint("proactive_video", __name__)

def _err(msg: str, code: int = 400):
    return jsonify({"ok": False, "error": msg}), code

@bp_proactive_video.route("/proactive/video/run", methods=["POST"])
def api_run():
    if run_once is None:
        return _err("autorunner not available", 500)
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        mode = (data.get("mode") or "subs").strip()
        topic: Optional[str] = data.get("topic")
        limit = int(data.get("limit") or 0) or None
        rep = run_once(mode=mode, topic=topic, limit=limit)
        return jsonify(rep)
    except Exception as e:
        return _err(f"exception: {e}", 500)

@bp_proactive_video.route("/proactive/video/state", methods=["GET"])
def api_state():
    if state is None:
        return _err("autorunner not available", 500)
    try:
        return jsonify(state())
    except Exception as e:
        return _err(f"exception: {e}", 500)

def register(app):
    """Podkhvatyvaetsya routes/register_all.py (drop-in)."""
# app.register_blueprint(bp_proactive_video)