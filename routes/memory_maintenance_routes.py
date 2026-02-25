# -*- coding: utf-8 -*-
"""routes/memory_maintenance_routes.py - REST dlya nochnogo obsluzhivaniya pamyati.

Endpoint:
  • POST /mem/maintenance/run {"heal":true,"compact":true,"snapshot":true}
  • GET /mem/maintenance/state

Mosty:
- Yavnyy: (Memory v†" Ekspluatatsiya) upravlenie TO cherez HTTP, integriruetsya s RuleHub cron.
- Skrytyy #1: (Infoteoriya v†" Nadezhnost) edinyy otchet o shagakh v state.json.
- Skrytyy #2: (Kibernetika v†" Nablyudaemost) otdelnye metriki na /metrics/memory_maintenance.

Zemnoy abzats:
Knopka "nochnoy sanchas": nazhal - proshlis po skladu.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_mem_maint = Blueprint("mem_maint", __name__)

try:
    from modules.memory.nightly_maintenance import run, last_state  # type: ignore
except Exception:
    run = last_state = None  # type: ignore

def register(app):
    app.register_blueprint(bp_mem_maint)

@bp_mem_maint.route("/mem/maintenance/run", methods=["POST"])
def api_run():
    if run is None:
        return jsonify({"ok": False, "error": "nightly_maintenance unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    return jsonify(run(data))

@bp_mem_maint.route("/mem/maintenance/state", methods=["GET"])
def api_state():
    if last_state is None:
        return jsonify({"ok": False, "error": "nightly_maintenance unavailable"}), 500
# return jsonify(last_state())