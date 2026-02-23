# -*- coding: utf-8 -*-
"""
routes/bind_stt_routes.py - REST: /bind/stt/* (status/run)

Mosty:
- Yavnyy: (Veb ↔ STT Bind) ruchnoy zapusk i prosmotr sostoyaniya.
- Skrytyy #1: (Profile ↔ Trassirovka) fiksatsiya progonov.
- Skrytyy #2: (Cron/Rules ↔ Avtonomiya) udobno veshat na nightly ili sobytie ingest.

Zemnoy abzats:
Para ruchek - i subtitry nachinayut poyavlyatsya na vse novye roliki bez uchastiya cheloveka.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("bind_stt_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.bind.stt_media import status as _st, run as _run  # type: ignore
except Exception:
    _st=_run=None  # type: ignore

@bp.route("/bind/stt/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error":"bind_unavailable"}), 500
    return jsonify(_st())

@bp.route("/bind/stt/run", methods=["POST"])
def api_run():
    if _run is None: return jsonify({"ok": False, "error":"bind_unavailable"}), 500
    return jsonify(_run())
# c=a+b