# -*- coding: utf-8 -*-
"""
routes/market_routes.py - REST: /market/gigs/* (scan/apply/list)

Mosty:
- Yavnyy: (Veb ↔ Market) sobrat vakansii i sformirovat otklik.
- Skrytyy #1: (Legal/Quota ↔ Ostorozhnost) soblyudaem limity i politiku.
- Skrytyy #2: (KG/Profile ↔ Navigatsiya/Audit) vse prozrachno i svyazno.

Zemnoy abzats:
Mini-voronka frilansa: «uvidela - zapisala - podgotovila pismo». Otpravka - uzhe po vybrannomu kanalu.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("market_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.market.gigs import scan as _scan, letter as _letter, list_items as _list  # type: ignore
except Exception:
    _scan=_letter=_list=None  # type: ignore

@bp.route("/market/gigs/scan", methods=["POST"])
def api_scan():
    if _scan is None: return jsonify({"ok": False, "error":"market_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_scan(list(d.get("items") or [])))

@bp.route("/market/gigs/apply", methods=["POST"])
def api_apply():
    if _letter is None: return jsonify({"ok": False, "error":"market_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_letter(dict(d.get("job") or {}), dict(d.get("profile") or {}), str(d.get("tone","concise"))))

@bp.route("/market/gigs/list", methods=["GET"])
def api_list():
    if _list is None: return jsonify({"ok": False, "error":"market_unavailable"}), 500
    limit=int(request.args.get("limit","50"))
    return jsonify(_list(limit))
# c=a+b