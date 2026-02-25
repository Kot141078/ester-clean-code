# -*- coding: utf-8 -*-
"""routes/dr321_routes.py - REST dlya offsayt-rezerva (3-2-1).

Mosty:
- Yavnyy: (Veb ↔ DR) zapustit rezerv, pokazat spisok, vernut arkhiv back.
- Skrytyy #1: (Audit ↔ Prozrachnost) vse cherez JSON; legko avtomatizirovat po cron/planirovschiku.
- Skrytyy #2: (Vyzhivanie ↔ Samosoborka) vmeste s self/rollback zakryvaet “podnyatsya after padeniya”.

Zemnoy abzats:
Odin klik - i kopiya na drugom diske/uzle gotova.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_dr = Blueprint("dr321", __name__)

try:
    from modules.dr.dr321 import list_offsite as _list, run_backup as _run, restore as _restore  # type: ignore
except Exception:
    _list = _run = _restore = None  # type: ignore

def register(app):
    app.register_blueprint(bp_dr)

@bp_dr.route("/dr321/list", methods=["GET"])
def api_list():
    if _list is None: return jsonify({"ok": False, "error":"dr321 unavailable"}), 500
    return jsonify(_list())

@bp_dr.route("/dr321/run", methods=["POST"])
def api_run():
    if _run is None: return jsonify({"ok": False, "error":"dr321 unavailable"}), 500
    return jsonify(_run())

@bp_dr.route("/dr321/restore", methods=["POST"])
def api_restore():
    if _restore is None: return jsonify({"ok": False, "error":"dr321 unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(_restore(str(d.get("archive",""))))
# c=a+b