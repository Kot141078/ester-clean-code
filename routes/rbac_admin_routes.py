# -*- coding: utf-8 -*-
"""
routes/rbac_admin_routes.py - REST: prosmotr/naznachenie roley.

Mosty:
- Yavnyy: (Veb ↔ RBAC) upravlyaem kartoy roley.
- Skrytyy #1: (Bootstrap ↔ Bezopasnost) trebuet sekret i/ili «pilyulyu».
- Skrytyy #2: (Integratsiya ↔ Ostorozhnost) drugie moduli mogut oprashivat allowed().

Zemnoy abzats:
Minimalnaya adminka roley - bez vneshney BD.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("rbac_admin_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from middleware.rbac import get_roles as _get, set_roles as _set, bootstrap_ok  # type: ignore
except Exception:
    _get=_set=bootstrap_ok=None  # type: ignore

@bp.route("/rbac/roles", methods=["GET"])
def api_get():
    if _get is None: return jsonify({"ok": False, "error":"rbac_unavailable"}), 500
    return jsonify({"ok": True, **_get()})

@bp.route("/rbac/roles", methods=["POST"])
def api_set():
    if _set is None: return jsonify({"ok": False, "error":"rbac_unavailable"}), 500
    d=request.get_json(True, True) or {}
    if not bootstrap_ok or not bootstrap_ok(str(d.get("secret",""))):
        return jsonify({"ok": False, "error":"bootstrap_denied"}), 403
    cur=_get()
    for it in d.get("assign") or []:
        cur["roles"][str(it.get("subject",""))]=str(it.get("role","viewer"))
    return jsonify(_set(cur))
# c=a+b