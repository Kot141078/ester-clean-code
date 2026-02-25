# -*- coding: utf-8 -*-
"""routes/resilience_health_routes.py - REST: /resilience/health/check.

Mosty:
- Yavnyy: (Veb ↔ Nadezhnost) bystryy status zdorovya.
- Skrytyy #1: (Panel ↔ Avtokatbek) ispolzuetsya guarded_apply.
- Skrytyy #2: (Cron ↔ Samoobsluzhivanie) mozhno stavit na taymer.

Zemnoy abzats:
Odin vyzov - i ponyatno, “zhivem” li my.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_health = Blueprint("resilience_health", __name__)

try:
    from modules.resilience.health import check as _check  # type: ignore
except Exception:
    _check=None  # type: ignore

def register(app):
    app.register_blueprint(bp_health)

@bp_health.route("/resilience/health/check", methods=["GET"])
def api_check():
    if _check is None: return jsonify({"ok": False, "error":"health_unavailable"}), 500
    return jsonify(_check())
# c=a+b