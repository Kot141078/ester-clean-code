# -*- coding: utf-8 -*-
"""routes/media_watch_routes.py - REST: config i tik votchera.

Mosty:
- Yavnyy: (Veb ↔ Avtonomiya) zadaem papki i zapuskaem prokhod.
- Skrytyy #1: (Memory ↔ Planirovschik) mozhno vyzyvat iz cron.
- Skrytyy #2: (Volya ↔ Actions) est deystviya dlya zapuska tika.

Zemnoy abzats:
Polozhil - razobrali. Po knopke or po taymeru.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_watch = Blueprint("media_watch_routes", __name__)

try:
    from modules.media.watchdog import get_config as _get, set_config as _set, tick as _tick  # type: ignore
except Exception:
    _get=_set=_tick=None  # type: ignore

def register(app):
    app.register_blueprint(bp_watch)

@bp_watch.route("/media/watch/config", methods=["GET"])
def api_get():
    if _get is None: return jsonify({"ok": False, "error":"watch_unavailable"}), 500
    return jsonify(_get())

@bp_watch.route("/media/watch/config", methods=["POST"])
def api_set():
    if _set is None: return jsonify({"ok": False, "error":"watch_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_set(list(d.get("dirs") or [])))

@bp_watch.route("/media/watch/tick", methods=["POST"])
def api_tick():
    if _tick is None: return jsonify({"ok": False, "error":"watch_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_tick(int(d.get("limit",10))))
# c=a+b