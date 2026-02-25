# -*- coding: utf-8 -*-
"""routes/opps_routes.py - REST: /opps/* (list/add/import/status)

Mosty:
- Yavnyy: (Veb ↔ Opps) CRUD i parsing vozmozhnostey.
- Skrytyy #1: (Outreach ↔ Potok) downstream generate predlozheniya.
- Skrytyy #2: (Invoices ↔ Kontur) statusy “won/invoiced/paid” soglasuyutsya s finansami.

Zemnoy abzats:
Eto knopki dlya CRM-bloknota: polozhil kartochku i dvigaesh ee po konveyeru do oplaty.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("opps_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.opps.hub import list_all as _list, add_or_update as _add, import_url as _import, set_status as _status  # type: ignore
except Exception:
    _list=_add=_import=_status=None  # type: ignore

@bp.route("/opps/list", methods=["GET"])
def api_list():
    if _list is None: return jsonify({"ok": False, "error":"opps_unavailable"}), 500
    st=request.args.get("status")
    return jsonify(_list(st))

@bp.route("/opps/add", methods=["POST"])
def api_add():
    if _add is None: return jsonify({"ok": False, "error":"opps_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_add(d))

@bp.route("/opps/import", methods=["POST"])
def api_import():
    if _import is None: return jsonify({"ok": False, "error":"opps_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_import(str(d.get("url","")), list(d.get("skills") or [])))

@bp.route("/opps/status", methods=["POST"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"opps_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_status(str(d.get("id","")), str(d.get("status","")), str(d.get("notes",""))))
# c=a+b