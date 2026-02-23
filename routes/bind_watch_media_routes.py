# -*- coding: utf-8 -*-
"""
routes/bind_watch_media_routes.py - REST: /bind/watch-media/* (config/status/run)

Mosty:
- Yavnyy: (Watch ↔ Media) knopki i API dlya avtozapuska inzhesta po papkam.
- Skrytyy #1: (Profile ↔ Prozrachnost) fiksatsiya konfiguratsiy i progonov.
- Skrytyy #2: (Cron/Rules ↔ Avtonomiya) legko zapuskat po taymeru ili sobytiyu.

Zemnoy abzats:
Para ruchek - i papka «vkhodyaschie video» nachinaet razbiratsya avtomaticheski, bez ruchnoy rutiny.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("bind_watch_media_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.bind.watch_media import config as _cfg, status as _st, run as _run  # type: ignore
except Exception:
    _cfg=_st=_run=None  # type: ignore

@bp.route("/bind/watch-media/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error":"bind_unavailable"}), 500
    return jsonify(_st())

@bp.route("/bind/watch-media/config", methods=["POST"])
def api_config():
    if _cfg is None: return jsonify({"ok": False, "error":"bind_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_cfg(list(d.get("roots") or []), list(d.get("patterns") or [])))

@bp.route("/bind/watch-media/run", methods=["POST"])
def api_run():
    if _run is None: return jsonify({"ok": False, "error":"bind_unavailable"}), 500
    d=request.get_json(True, True) or {}
    roots=list(d.get("roots") or []) if "roots" in d else None
    pats =list(d.get("patterns") or []) if "patterns" in d else None
    return jsonify(_run(roots, pats))
# c=a+b