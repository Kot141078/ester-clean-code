# -*- coding: utf-8 -*-
"""
routes/actions_registry_routes.py - REST dlya raboty s ActionRegistry++.

Mosty:
- Yavnyy: (Veb ↔ Reestr) spisok/status/universalnyy zapusk po imeni.
- Skrytyy #1: (Volya ↔ Inspektsiya) UI/mysli mogut videt kakie eksheny dostupny.
- Skrytyy #2: (Profile ↔ Log) vyzovy uzhe logiruyutsya JSONL v module.

Zemnoy abzats:
Edinaya «knopochnaya panel»: «chto est?», «kak zhivet?», «zapusti vot eto po imeni».

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
bp=Blueprint("actions_registry_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.thinking.action_registry import list_actions as _list, status as _status, run as _run  # type: ignore
except Exception:
    _list=_status=_run=None  # type: ignore

@bp.route("/thinking/actions/list", methods=["GET"])
def api_list():
    if _list is None: return jsonify({"ok": False, "error":"registry_unavailable"}), 500
    return jsonify(_list())

@bp.route("/thinking/actions/status", methods=["GET"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"registry_unavailable"}), 500
    return jsonify(_status())

@bp.route("/thinking/action/run", methods=["POST"])
def api_run():
    if _run is None: return jsonify({"ok": False, "error":"registry_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_run(str(d.get("name","")), dict(d.get("args") or {})))
# c=a+b