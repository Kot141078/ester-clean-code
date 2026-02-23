# -*- coding: utf-8 -*-
"""
routes/ops_hiring_routes.py - REST dlya formirovaniya skoupa «mikro-nayma».

Endpointy:
  • POST /ops/hiring/scope {"role","tasks":[], "budget_cap": number}

Mosty:
- Yavnyy: (Operatsii ↔ Lyudi) bystro formiruem TZ.
- Skrytyy #1: (Ekonomika ↔ Kontrol) byudzhet ogovoren zaranee.
- Skrytyy #2: (Myshlenie ↔ Praktika) kaskad-plan mozhet predlagat naym kak strategiyu.

Zemnoy abzats:
Eto forma «chto nuzhno sdelat i za skolko» - bez lishnikh tseremoniy.

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict, List
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_hiring = Blueprint("ops_hiring", __name__)

try:
    from modules.ops.hiring_sim import scope  # type: ignore
except Exception:
    scope = None  # type: ignore

def register(app):
    app.register_blueprint(bp_hiring)

@bp_hiring.route("/ops/hiring/scope", methods=["POST"])
def api_scope():
    if scope is None:
        return jsonify({"ok": False, "error":"hiring module unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    role = str(d.get("role","")).strip()
    tasks: List[str] = list(d.get("tasks") or [])
    cap = float(d.get("budget_cap", 0))
    return jsonify(scope(role, tasks, cap))