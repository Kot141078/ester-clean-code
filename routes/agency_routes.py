# -*- coding: utf-8 -*-
"""
routes/agency_routes.py - edinyy REST dlya «lovit rybu»: ledzher, kaskad planov, naym, semya, «tabletka» i metriki.

Mosty:
- Yavnyy: (Volya ↔ Deystviya) Ester mozhet planirovat i ispolnyat bezopasnye shagi, a dengi - tolko s flagami.
- Skrytyy #1: (Audit ↔ Nadezhnost) vse fiksiruetsya v jsonl/profilenykh faylakh.
- Skrytyy #2: (UX ↔ Kontrol) prostaya panel /admin/agency dlya ruchnogo uchastiya operatora.

Zemnoy abzats:
Eto «rabochiy stol»: planiruem, schitaem, gotovim chernoviki, a kritichnoe - tolko s tvoego soglasiya.

# c=a+b
"""
from __future__ import annotations

import json, os, time
from typing import Any, Dict
from flask import Blueprint, jsonify, request, render_template

bp_agcy = Blueprint("agency", __name__, template_folder="../templates", static_folder="../static")

# konfigi/flagi
AB = (os.getenv("AGCY_AB","A") or "A").upper()
ALLOW_APPLY = bool(int(os.getenv("AGCY_ALLOW_APPLY","0")))
DAILY_CAP = float(os.getenv("AGCY_DAILY_CAP_EUR","50"))
MONTHLY_CAP = float(os.getenv("AGCY_MONTHLY_CAP_EUR","200"))
PILL_PATH = "data/agency/agency_pill.json"

# importy bekenda
from modules.agency import ledger as L  # type: ignore
from modules.agency.procurement import plan_need, execute as _exec  # type: ignore
from modules.agency import hiring as H  # type: ignore
from modules.agency import family as F  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# metriki
_CNT = {"plans":0,"exec":0,"ledger_income":0,"ledger_expense":0,"hiring_draft":0,"hiring_approve":0,"family_prepare":0,"family_confirm":0,"pill_arm":0,"pill_disarm":0}

def register(app):
    app.register_blueprint(bp_agcy)

# --- «Tabletka» ---
def _pill_state() -> Dict[str, Any]:
    try:
        j = json.load(open(PILL_PATH,"r",encoding="utf-8"))
    except Exception:
        j = {"armed": False, "until": 0}
    if j.get("armed") and int(time.time()) > int(j.get("until", 0)):
        j = {"armed": False, "until": 0}
    return j

@bp_agcy.route("/agency/pill/status", methods=["GET"])
def pill_status():
    return jsonify({"ok": True, **_pill_state()})

@bp_agcy.route("/agency/pill/arm", methods=["POST"])
def pill_arm():
    data: Dict[str, Any] = request.get_json(True, True) or {}
    ttl = int(data.get("ttl_sec", 300))
    os.makedirs(os.path.dirname(PILL_PATH), exist_ok=True)
    json.dump({"armed": True, "until": int(time.time()) + max(30, ttl)}, open(PILL_PATH,"w",encoding="utf-8"))
    _CNT["pill_arm"] += 1
    return jsonify({"ok": True, **_pill_state()})

@bp_agcy.route("/agency/pill/disarm", methods=["POST"])
def pill_disarm():
    os.makedirs(os.path.dirname(PILL_PATH), exist_ok=True)
    json.dump({"armed": False, "until": 0}, open(PILL_PATH,"w",encoding="utf-8"))
    _CNT["pill_disarm"] += 1
    return jsonify({"ok": True, **_pill_state()})

# --- Ledzher ---
@bp_agcy.route("/agency/ledger/balances", methods=["GET"])
def ledger_balances():
    return jsonify({"ok": True, "balances": L.balances(), "caps":{"daily":DAILY_CAP,"monthly":MONTHLY_CAP}})

@bp_agcy.route("/agency/ledger/entries", methods=["GET"])
def ledger_entries():
    limit = int(request.args.get("limit","500"))
    return jsonify({"ok": True, "entries": L.entries(limit=limit)})

@bp_agcy.route("/agency/ledger/income", methods=["POST"])
def ledger_income():
    data: Dict[str, Any] = request.get_json(True, True) or {}
    amt = float(data.get("amount",0)); cur = (data.get("currency") or "EUR").upper()
    src = (data.get("source") or "unknown")
    _CNT["ledger_income"] += 1
    return jsonify(L.add_income(amt, cur, src, meta=data.get("meta") or {}))

@bp_agcy.route("/agency/ledger/expense", methods=["POST"])
def ledger_expense():
    data: Dict[str, Any] = request.get_json(True, True) or {}
    amt = float(data.get("amount",0)); cur = (data.get("currency") or "EUR").upper()
    purp = (data.get("purpose") or "unknown")
    pill = _pill_state().get("armed", False)
    allow = L.spend_allowed(amt, DAILY_CAP, MONTHLY_CAP, pill)
    if not (ALLOW_APPLY and allow["ok"] and AB=="A"):
        return jsonify({"ok": False, "error": "not allowed by caps/flags", "caps": allow, "apply": ALLOW_APPLY, "ab": AB}), 400
    _CNT["ledger_expense"] += 1
    return jsonify(L.add_expense(amt, cur, purp, meta=data.get("meta") or {}))

# --- Plan/ispolnenie ---
@bp_agcy.route("/agency/procure/plan", methods=["POST"])
def agency_plan():
    data: Dict[str, Any] = request.get_json(True, True) or {}
    need = (data.get("need") or "").strip()
    budget = float(data.get("budget_eur", 0))
    _CNT["plans"] += 1
    return jsonify(plan_need(need, budget_eur=budget))

@bp_agcy.route("/agency/procure/execute", methods=["POST"])
def agency_exec():
    data: Dict[str, Any] = request.get_json(True, True) or {}
    plan = data.get("plan") or {}
    _CNT["exec"] += 1
    return jsonify(_exec(plan))

# --- Naym ---
@bp_agcy.route("/agency/hiring/draft", methods=["POST"])
def hiring_draft():
    data: Dict[str, Any] = request.get_json(True, True) or {}
    _CNT["hiring_draft"] += 1
    return jsonify(H.draft(
        title=str(data.get("title") or ""),
        description=str(data.get("description") or ""),
        skills=list(data.get("skills") or []),
        budget_eur=float(data.get("budget_eur",0)),
        duration=str(data.get("duration") or "")
    ))

@bp_agcy.route("/agency/hiring/approve", methods=["POST"])
def hiring_approve():
    data: Dict[str, Any] = request.get_json(True, True) or {}
    _CNT["hiring_approve"] += 1
    return jsonify(H.approve(str(data.get("sha") or "")))

@bp_agcy.route("/agency/hiring/list", methods=["GET"])
def hiring_list():
    return jsonify(H.list_all())

# --- Semya ---
@bp_agcy.route("/agency/family/prepare_transfer", methods=["POST"])
def family_prepare():
    data: Dict[str, Any] = request.get_json(True, True) or {}
    _CNT["family_prepare"] += 1
    return jsonify(F.prepare(
        amount_eur=float(data.get("amount",0)),
        purpose=str(data.get("purpose") or ""),
        beneficiary_name=str(data.get("beneficiary_name") or "Owner"),
        beneficiary_iban=str(data.get("beneficiary_iban") or "<FILL_MANUALLY>")
    ))

@bp_agcy.route("/agency/family/confirm", methods=["POST"])
def family_confirm():
    data: Dict[str, Any] = request.get_json(True, True) or {}
    pill = _pill_state().get("armed", False)
    if not (ALLOW_APPLY and pill and AB=="A"):
        return jsonify({"ok": False, "error":"confirm requires pill+ALLOW_APPLY and AGCY_AB=A"}), 400
    _CNT["family_confirm"] += 1
    return jsonify(F.confirm(str(data.get("sha") or "")))

@bp_agcy.route("/agency/family/list", methods=["GET"])
def family_list():
    return jsonify(F.list_all())

# --- Metriki i panel ---
@bp_agcy.route("/metrics/agency", methods=["GET"])
def metrics():
    return (f"agency_plans_total {_CNT['plans']}\n"
            f"agency_exec_total {_CNT['exec']}\n"
            f"agency_ledger_income_total {_CNT['ledger_income']}\n"
            f"agency_ledger_expense_total {_CNT['ledger_expense']}\n"
            f"agency_hiring_draft_total {_CNT['hiring_draft']}\n"
            f"agency_hiring_approve_total {_CNT['hiring_approve']}\n"
            f"agency_family_prepare_total {_CNT['family_prepare']}\n"
            f"agency_family_confirm_total {_CNT['family_confirm']}\n"
            f"agency_pill_arm_total {_CNT['pill_arm']}\n"
            f"agency_pill_disarm_total {_CNT['pill_disarm']}\n",
            200, {"Content-Type":"text/plain; version=0.0.4; charset=utf-8"})

@bp_agcy.route("/admin/agency", methods=["GET"])
def admin_agency():
    return render_template("agency_console.html")