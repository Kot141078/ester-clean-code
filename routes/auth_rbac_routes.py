# -*- coding: utf-8 -*-
"""
routes/auth_rbac_routes.py - REST: pokazat tekuschie roli/subekt (dlya UI/diagnostiki).

Mosty:
- Yavnyy: (Veb ↔ RBAC) daet UI bystryy sposob ponyat «kto ya dlya sistemy?».
- Skrytyy #1: (Politiki ↔ Inspektsiya) pomogaet pri otladke prav.
- Skrytyy #2: (Memory ↔ Profile) pri neobkhodimosti rasshiryaetsya logirovaniem.

Zemnoy abzats:
Eto kak posmotret propusk na svet: vidno imya i spisok dopuskov.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
bp = Blueprint("auth_rbac_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.auth.rbac import get_current_roles  # type: ignore
except Exception:
    get_current_roles=None  # type: ignore

@bp.route("/auth/rbac/status", methods=["GET"])
def api_rbac_status():
    if get_current_roles is None:
        return jsonify({"ok": False, "error":"rbac_unavailable"}), 500
    return jsonify({"ok": True, "roles": get_current_roles()})
# c=a+b