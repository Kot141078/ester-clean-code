# -*- coding: utf-8 -*-
"""routes/invoice_routes.py - REST: /finance/invoice/create|get

Mosty:
- Yavnyy: (Veb ↔ Finansy) podgotovka scheta na side Ester.
- Skrytyy #1: (Profile/RAG ↔ Prozrachnost/Poisk) schet shtampuetsya i indeksiruetsya.
- Skrytyy #2: (Garage/Portfolio ↔ Vitrina) gotovye HTML mozhno klast v portfolio.

Zemnoy abzats:
Sdelali rabotu - bystro vypustili schet - prilozhili k pismu. Bez vneshnikh servisov i bez ozhidaniy.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, send_file
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("invoice_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.finance.invoice import create as _create, get as _get  # type: ignore
except Exception:
    _create=_get=None  # type: ignore

@bp.route("/finance/invoice/create", methods=["POST"])
def api_create():
    if _create is None: return jsonify({"ok": False, "error":"invoice_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_create(d))

@bp.route("/finance/invoice/get", methods=["GET"])
def api_get():
    if _get is None: return jsonify({"ok": False, "error":"invoice_unavailable"}), 500
    iid=str(request.args.get("id","")); fmt=str(request.args.get("format","md"))
    rep=_get(iid, fmt)
    if not rep.get("ok"): return jsonify(rep), 404
    return send_file(rep["path"], mimetype="text/plain; charset=utf-8")
# c=a+b