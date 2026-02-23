# -*- coding: utf-8 -*-
"""
routes/self_plan_routes.py - REST: plan pod tsel i ego vypolnenie (po umolchaniyu bezopasnyy dry-run).

Endpointy:
  • POST /self/plan {"goal","constraints"?}
  • POST /self/act/execute {"plan","safe"?:true}

Mosty:
- Yavnyy: (Volya ↔ Deystviya) edinoe mesto, gde i tsel formuliruetsya, i plan gotovitsya/vypolnyaetsya.
- Skrytyy #1: (Inzheneriya ↔ Prozrachnost) rezultat plana prigoden dlya logirovaniya/audita.
- Skrytyy #2: (UX ↔ Kontrol) bezopasnyy rezhim po umolchaniyu.

Zemnoy abzats:
Eto knopki «splaniruy» i «vypolni»: po umolchaniyu tolko primeryaetsya, no mozhet i sdelat.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_self_plan = Blueprint("self_plan", __name__)

try:
    from modules.self.plan_orchestrator import make_plan, execute  # type: ignore
except Exception:
    make_plan = execute = None  # type: ignore

def register(app):
    app.register_blueprint(bp_self_plan)

@bp_self_plan.route("/self/plan", methods=["POST"])
def api_plan():
    if make_plan is None:
        return jsonify({"ok": False, "error": "plan orchestrator unavailable"}), 500
    data: Dict[str, Any] = request.get_json(True, True) or {}
    goal = (data.get("goal") or "").strip()
    cons = data.get("constraints") or {}
    if not goal:
        return jsonify({"ok": False, "error": "goal is required"}), 400
    return jsonify(make_plan(goal, cons))

@bp_self_plan.route("/self/act/execute", methods=["POST"])
def api_exec():
    if execute is None:
        return jsonify({"ok": False, "error": "plan orchestrator unavailable"}), 500
    data: Dict[str, Any] = request.get_json(True, True) or {}
    plan = data.get("plan") or {}
    safe = bool(data.get("safe", True))
    return jsonify(execute(plan, safe=safe))