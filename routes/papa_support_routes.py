# -*- coding: utf-8 -*-
"""
routes/papa_support_routes.py - Bystrye stsenarii «podderzhat Papu» (cherez agentstvo/semyu), bez realnykh platezhey.

Mosty:
- Yavnyy: (Ekonomika ↔ Semya) gotovim chernoviki perevodov i rezervy pod limitami.
- Skrytyy #1: (Kibernetika ↔ Kontrol) ALLOW_APPLY + «tabletka» → tolko osoznannye deystviya.
- Skrytyy #2: (Myshlenie ↔ Memory) operatsii logiruyutsya i mogut uchityvatsya v refleksii.

Zemnoy abzats:
Eto kak «bystrye knopki»: prigotovit perevod Pape, zafiksirovat namerenie i dozhdatsya tvoego OK.

# c=a+b
"""
from __future__ import annotations
import os
from typing import Any, Dict
from flask import Blueprint, jsonify, request, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_papa_sup = Blueprint("papa_support", __name__, template_folder="../templates", static_folder="../static")

ALLOW_APPLY = bool(int(os.getenv("AGCY_ALLOW_APPLY","0")))

try:
    from modules.agency.family import prepare as f_prepare, confirm as f_confirm, list_all as f_list  # type: ignore
    from modules.agency.ledger import add_expense, spend_allowed  # type: ignore
    from modules.policy.papa_priority import status as pol_status  # type: ignore
except Exception:
    f_prepare = f_confirm = f_list = None  # type: ignore
    add_expense = spend_allowed = None  # type: ignore
    pol_status = None  # type: ignore

def register(app):
    app.register_blueprint(bp_papa_sup)

@bp_papa_sup.route("/agency/papa/support/plan", methods=["POST"])
def plan():
    if f_prepare is None: return jsonify({"ok": False, "error":"agency.family unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    amt = float(d.get("amount_eur", 0)); purpose = str(d.get("purpose","pomosch Pape"))
    j = f_prepare(amount_eur=amt, purpose=purpose, beneficiary_name="Owner")
    # fiksiruem «raskhod-rezerv» (bez realnogo spisaniya - prosto kak namerenie)
    caps = spend_allowed(amt, float(os.getenv("AGCY_DAILY_CAP_EUR","50")), float(os.getenv("AGCY_MONTHLY_CAP_EUR","200")), pol_status().get("pill",{}).get("armed", False)) if spend_allowed and pol_status else {"ok": False}
    return jsonify({"ok": True, "draft": j, "caps": caps})

@bp_papa_sup.route("/agency/papa/support/execute", methods=["POST"])
def execute():
    if f_confirm is None: return jsonify({"ok": False, "error":"agency.family unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    sha = str(d.get("sha",""))
    pol = pol_status() if pol_status else {"pill":{"armed":False}}
    if not (ALLOW_APPLY and pol.get("pill",{}).get("armed", False)):
        return jsonify({"ok": False, "error":"require AGCY_ALLOW_APPLY=1 and papa-policy pill armed"}), 400
    return jsonify(f_confirm(sha))

@bp_papa_sup.route("/admin/papa", methods=["GET"])
def admin_papa():
    return render_template("papa_console.html")
# c=a+b