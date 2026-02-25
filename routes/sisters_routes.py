# -*- coding: utf-8 -*-
"""routes/sisters_routes.py - REST: spisok/registratsiya sister i vydacha zadach.

Mosty:
- Yavnyy: (Veb ↔ Sestry) tsentralizovannoe upravlenie raspredeleniem.
- Skrytyy #1: (Profile ↔ Trassirovka) fiksiruem vydachi i iskhody.
- Skrytyy #2: (Rules/Cron ↔ Avtonomiya) legko vyazhetsya s pravilami/kronom.

Zemnoy abzats:
Odin POST - i nuzhnaya sestra poluchila poruchenie; the result is visible immediately.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("sisters_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.sisters.registry import list_nodes as _list, upsert as _upsert, assign as _assign  # type: ignore
except Exception:
    _list=_upsert=_assign=None  # type: ignore

@bp.route("/sisters/list", methods=["GET"])
def api_list():
    if _list is None: return jsonify({"ok": False, "error":"sisters_unavailable"}), 500
    return jsonify(_list())

@bp.route("/sisters/upsert", methods=["POST"])
def api_upsert():
    if _upsert is None: return jsonify({"ok": False, "error":"sisters_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_upsert(str(d.get("name","")), str(d.get("base_url","")), list(d.get("caps") or [])))

@bp.route("/sisters/assign", methods=["POST"])
def api_assign():
    if _assign is None: return jsonify({"ok": False, "error":"sisters_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_assign(str(d.get("name","")), str(d.get("path","")), dict(d.get("payload") or {})))
# c=a+b