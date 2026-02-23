# -*- coding: utf-8 -*-
"""
routes/thinking_cascade_routes.py - REST dlya kaskadnogo planirovaniya i bezopasnogo vypolneniya.

Endpointy:
  • POST /thinking/cascade/plan {"goal","budget"?:number}
  • POST /thinking/cascade/execute {"plan":{...}}
  • GET  /metrics/thinking_cascade

Mosty:
- Yavnyy: (Myshlenie ↔ Operatsii) formiruem plan i zapuskaem bezopasnye shagi.
- Skrytyy #1: (Ekonomika ↔ Zakupki) stykuemsya s koshelkom/zadaniyami.
- Skrytyy #2: (Samoizmenenie ↔ Kontrol) self.codegen rabotaet cherez suschestvuyuschuyu pesochnitsu s predokhranitelyami.

Zemnoy abzats:
Eto «mozgovoy kaskad»: ponyat, vybrat put, raspisat zadachi i sdelat to, chto mozhno sdelat pryamo seychas.

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_cascade = Blueprint("thinking_cascade", __name__)

try:
    from modules.thinking.cascade_planner import make_plan, execute  # type: ignore
except Exception:
    make_plan = execute = None  # type: ignore

_CNT = {"plans":0, "execs":0}

def register(app):
    app.register_blueprint(bp_cascade)

@bp_cascade.route("/thinking/cascade/plan", methods=["POST"])
def api_plan():
    if make_plan is None:
        return jsonify({"ok": False, "error": "cascade planner unavailable"}), 500
    data: Dict[str, Any] = request.get_json(True, True) or {}
    goal = (data.get("goal") or "").strip()
    budget = data.get("budget", None)
    rep = make_plan(goal, budget)
    if rep.get("ok"): _CNT["plans"] += 1
    return jsonify(rep)

@bp_cascade.route("/thinking/cascade/execute", methods=["POST"])
def api_exec():
    if execute is None:
        return jsonify({"ok": False, "error": "cascade planner unavailable"}), 500
    data: Dict[str, Any] = request.get_json(True, True) or {}
    plan = data.get("plan") or {}
    rep = execute(plan)
    if rep.get("ok"): _CNT["execs"] += 1
    return jsonify(rep)

@bp_cascade.route("/metrics/thinking_cascade", methods=["GET"])
def metrics():
    return (f"thinking_cascade_plans_total {_CNT['plans']}\n"
            f"thinking_cascade_execs_total {_CNT['execs']}\n",
            200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})