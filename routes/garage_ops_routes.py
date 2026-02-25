# -*- coding: utf-8 -*-
"""routes/garage_ops_routes.py - REST: propozal, skelet, schet, portfolio, flot-assayn.

Mosty:
- Yavnyy: (Veb ↔ Operatsii garazha) “s odnoy knopki” ves tsikl ot offera do scheta.
- Skrytyy #1: (Memory ↔ Profile) operatsii pishut profile.
- Skrytyy #2: (Volya ↔ Avtonomiya) vse dostupno ekshenam.

Zemnoy abzats:
Panel upravleniya v masterskoy: sobrat offer, razvernut karkas, vypisat schet, pokazat portfolio, razdat zadachi.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("garage_ops_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.garage.proposals import proposal_build as _build, scaffold_create as _scf, invoice_make as _inv, portfolio_list as _port, fleet_assign as _fleet  # type: ignore
except Exception:
    _build=_scf=_inv=_port=_fleet=None  # type: ignore

@bp.route("/garage/proposal/build", methods=["POST"])
def api_proposal_build():
    if _build is None: return jsonify({"ok": False, "error":"garage_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_build(str(d.get("id","")), bool(d.get("include_scaffold", False))))

@bp.route("/garage/project/scaffold", methods=["POST"])
def api_scaffold():
    if _scf is None: return jsonify({"ok": False, "error":"garage_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_scf(str(d.get("name","")), str(d.get("stack","python-web"))))

@bp.route("/garage/invoice/make", methods=["POST"])
def api_invoice_make():
    if _inv is None: return jsonify({"ok": False, "error":"garage_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_inv(str(d.get("invoice_id","INV-TEST")), dict(d.get("client") or {}), list(d.get("items") or []), str(d.get("currency","EUR"))))

@bp.route("/garage/portfolio/list", methods=["GET"])
def api_portfolio():
    if _port is None: return jsonify({"ok": False, "error":"garage_unavailable"}), 500
    return jsonify(_port())

@bp.route("/garage/fleet/assign", methods=["POST"])
def api_fleet_assign():
    if _fleet is None: return jsonify({"ok": False, "error":"garage_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_fleet(list(d.get("tasks") or []), list(d.get("peers") or [])))
# c=a+b