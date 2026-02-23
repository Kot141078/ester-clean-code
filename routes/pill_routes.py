# -*- coding: utf-8 -*-
"""
routes/pill_routes.py - REST: /pill/* - upravlenie «pilyulyami».

Mosty:
- Yavnyy: (UI/Volya ↔ Pillbox) zapros/spisok/approve/deny/status.
- Skrytyy #1: (Profile ↔ Trassirovka) bazovyy modul pishet zhurnal.
- Skrytyy #2: (Hub/Rules ↔ Avtonomiya) mozhno vyzyvat iz paneli i planirovschika.

Zemnoy abzats:
Prostaya ochered «na podtverzhdenie»: posmotret, nazhat «da» ili «net», i deystvie proydet/zablokiruetsya.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("pill_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.policy.pillbox import status as _st, list_latest as _ls, request as _rq, approve as _ap, deny as _dn  # type: ignore
except Exception:
    _st=_ls=_rq=_ap=_dn=None  # type: ignore

@bp.route("/pill/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error":"pill_unavailable"}), 500
    return jsonify(_st())

@bp.route("/pill/list", methods=["GET"])
def api_list():
    if _ls is None: return jsonify({"ok": False, "error":"pill_unavailable"}), 500
    lim=int(request.args.get("limit","50") or "50")
    return jsonify(_ls(lim))

@bp.route("/pill/request", methods=["POST"])
def api_request():
    if _rq is None: return jsonify({"ok": False, "error":"pill_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_rq(str(d.get("method","POST")), str(d.get("path","/")), str(d.get("sha256","")), d.get("ttl"), d.get("note"), request.remote_addr or ""))

@bp.route("/pill/approve", methods=["POST"])
def api_approve():
    if _ap is None: return jsonify({"ok": False, "error":"pill_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_ap(str(d.get("id","")), d.get("approver")))

@bp.route("/pill/deny", methods=["POST"])
def api_deny():
    if _dn is None: return jsonify({"ok": False, "error":"pill_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_dn(str(d.get("id","")), d.get("reason")))
# c=a+b