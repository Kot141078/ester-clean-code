# -*- coding: utf-8 -*-
"""
routes/resilience_rollback_routes.py - REST: /resilience/rollback/paths.

Mosty:
- Yavnyy: (Veb ↔ Otkat) yavnyy i adresnyy rollback.
- Skrytyy #1: (Guarded Apply ↔ Integratsiya) ispolzuetsya obertkoy.
- Skrytyy #2: (UX ↔ Panel) prozrachen dlya operatora.

Zemnoy abzats:
Prostoy sposob vernut konkretnye fayly k proshlomu sostoyaniyu.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_rb = Blueprint("resilience_rollback", __name__)

try:
    from modules.resilience.rollback import rollback_paths as _rb  # type: ignore
except Exception:
    _rb=None  # type: ignore

def register(app):
    app.register_blueprint(bp_rb)

@bp_rb.route("/resilience/rollback/paths", methods=["POST"])
def api_rb():
    if _rb is None: return jsonify({"ok": False, "error":"rollback_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_rb(list(d.get("paths") or [])))
# c=a+b