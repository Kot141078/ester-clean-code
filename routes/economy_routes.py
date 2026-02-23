# -*- coding: utf-8 -*-
"""
routes/economy_routes.py - REST dlya modulya ekonomiki (koshelek i ledzher).

Endpointy:
  • GET  /economy/ledger                  (Sostoyanie koshelka)
  • GET  /economy/ledger/status             (Status ledzhera)
  • POST /economy/ledger/append              {"kind","cat","amount","currency","note"}
  • POST /economy/ledger/transfer            {"from","to","amount","note"?}
  • POST /economy/ledger/reserve             {"account","amount","reason"}
  • POST /economy/ledger/approve             {"reserve_id"}
  • POST /economy/ledger/spend               {"account","amount","sink","reserve_id"?}

Mosty:
- Yavnyy #1: (Ekonomika ↔ Operatsii) dengi dvigayutsya po prozrachnym pravilam.
- Yavnyy #2: (Veb ↔ Ekonomika) posmotret balans, dobavit zapis, sovmestimo s HTML-panelyu.
- Skrytyy #1: (Kibernetika/Audit ↔ Kontrol) porog/odobrenie uderzhivayut krupnye traty; JSON-otvety dlya UI.
- Skrytyy #2: (Audit ↔ Podotchetnost) istoriya operatsiy sokhranyaetsya.
- Skrytyy #3: (Politiki ↔ Ostorozhnost) sochetaetsya s printsipom cautious_freedom i mozhet byt ogranicheno cherez CostFence.

Zemnoy abzats:
Gde moi dengi, Zin? Zdes.
Eto kassa. Vidim balans, otkladyvaem na pokupku, tratim tolko posle «da». Kuda ushlo i otkuda prishlo - bystro vidno.

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_economy = Blueprint("economy", __name__)

try:
    # Funktsii iz modulya koshelka
    from modules.economy.ledger import get_state, transfer, reserve, approve, spend  # type: ignore
    # Funktsii iz modulya ledzhera
    from modules.economy.ledger import status as _status, append as _append  # type: ignore
except Exception:
    get_state = transfer = reserve = approve = spend = None  # type: ignore
    _status = _append = None  # type: ignore

def register(app):
    """Registriruet etot blueprint v prilozhenii Flask."""
    app.register_blueprint(bp_economy)

# --- Endpointy dlya chteniya ---

@bp_economy.route("/economy/ledger", methods=["GET"])
def api_state():
    """Vozvraschaet polnoe sostoyanie koshelka."""
    if get_state is None: return jsonify({"ok": False, "error":"ledger unavailable"}), 500
    return jsonify(get_state())

@bp_economy.route("/economy/ledger/status", methods=["GET"])
def api_status():
    """Vozvraschaet bazovyy status ledzhera."""
    if _status is None: return jsonify({"ok": False, "error":"ledger unavailable"}), 500
    return jsonify(_status())

# --- Endpointy dlya zapisi i operatsiy ---

@bp_economy.route("/economy/ledger/append", methods=["POST"])
def api_append():
    """Dobavlyaet zapis v ledzher (dokhod/raskhod)."""
    if _append is None: return jsonify({"ok": False, "error":"ledger unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_append(
        str(d.get("kind","expense")),
        str(d.get("cat","misc")),
        float(d.get("amount",0.0)),
        str(d.get("currency","EUR")),
        str(d.get("note",""))
    ))

@bp_economy.route("/economy/ledger/transfer", methods=["POST"])
def api_transfer():
    """Perevodit sredstva mezhdu schetami."""
    if transfer is None: return jsonify({"ok": False, "error":"ledger unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(transfer(
        str(d.get("from")),
        str(d.get("to")),
        float(d.get("amount",0)),
        str(d.get("note",""))
    ))

@bp_economy.route("/economy/ledger/reserve", methods=["POST"])
def api_reserve():
    """Rezerviruet summu na schete dlya buduschey traty."""
    if reserve is None: return jsonify({"ok": False, "error":"ledger unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(reserve(
        str(d.get("account")),
        float(d.get("amount",0)),
        str(d.get("reason",""))
    ))

@bp_economy.route("/economy/ledger/approve", methods=["POST"])
def api_approve():
    """Odobryaet sozdannyy ranee rezerv."""
    if approve is None: return jsonify({"ok": False, "error":"ledger unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(approve(str(d.get("reserve_id"))))

@bp_economy.route("/economy/ledger/spend", methods=["POST"])
def api_spend():
    """Spisyvaet sredstva so scheta (vozmozhno, ispolzuya rezerv)."""
    if spend is None: return jsonify({"ok": False, "error":"ledger unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(spend(
        str(d.get("account")),
        float(d.get("amount",0)),
        str(d.get("sink","")),
        d.get("reserve_id")
    ))