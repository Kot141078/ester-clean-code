# -*- coding: utf-8 -*-
"""routes/rbac_routes.py - REST: naznachenie roley i trebovaniya k routetam.

Mosty:
- Yavnyy: (Veb ↔ RBAC) upravlyaem polzovatelyami i pravilami.
- Skrytyy #1: (Integratsiya ↔ AppOps+) mozhno trebovat rol admin dlya /app/discover/register.
- Skrytyy #2: (UX ↔ Panel) easy svyazat s UI.

Zemnoy abzats:
“Who is the admin?” - nastraivaetsya odnoy ruchkoy.
# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_rbac = Blueprint("rbac_routes", __name__)

try:
    from modules.security.rbac import assign as _assign, require as _require, policy as _policy, check_access as _check  # type: ignore
except Exception:
    _assign=_require=_policy=_check = None  # type: ignore

def register(app):
    app.register_blueprint(bp_rbac)

@bp_rbac.route("/rbac/policy", methods=["GET"])
def api_policy():
    if _policy is None: return jsonify({"ok": False, "error":"rbac_unavailable"}), 500
    return jsonify(_policy())

@bp_rbac.route("/rbac/assign", methods=["POST"])
def api_assign():
    if _assign is None: return jsonify({"ok": False, "error":"rbac_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_assign(str(d.get("user","")), str(d.get("role","viewer"))))

@bp_rbac.route("/rbac/require", methods=["POST"])
def api_require():
    if _require is None: return jsonify({"ok": False, "error":"rbac_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_require(str(d.get("pattern","^$")), str(d.get("min_role","viewer"))))
# c=a+b