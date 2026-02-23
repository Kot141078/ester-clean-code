# -*- coding: utf-8 -*-
"""
routes/thinking_guard_routes.py - REST: storozh deystviy (status/nastroyka/test).

Mosty:
- Yavnyy: (Veb ↔ Mysli) upravlyaet limitami, taymautami i daet bezopasnyy zapusk.
- Skrytyy #1: (Memory ↔ Profile) storozh uzhe logiruet akty/taymauty.
- Skrytyy #2: (RBAC ↔ Ostorozhnost) konfig - dlya operator/admin (esli RBAC vklyuchen).

Zemnoy abzats:
Kak «schitok» s avtomatami: mozhno podkrutit nominal ili vyklyuchit problemnuyu liniyu.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("thinking_guard_routes", __name__)

def register(app):
    app.register_blueprint(bp)

def _rbac_ok(roles):
    if (os.getenv("RBAC_REQUIRED","true").lower()=="false"): return True
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(roles)
    except Exception:
        return True

try:
    from modules.thinking.act_guard import status as _status, set_config as _setcfg, run as _run  # type: ignore
except Exception:
    _status=_setcfg=_run=None  # type: ignore

@bp.route("/thinking/guard/status", methods=["GET"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"guard_unavailable"}), 500
    return jsonify(_status())

@bp.route("/thinking/guard/config", methods=["POST"])
def api_config():
    if _setcfg is None: return jsonify({"ok": False, "error":"guard_unavailable"}), 500
    if not _rbac_ok(["operator","admin"]): return jsonify({"ok": False, "error":"forbidden"}), 403
    d=request.get_json(True, True) or {}
    return jsonify(_setcfg(str(d.get("name","")), d.get("timeout"), d.get("wip"), d.get("enabled")))

@bp.route("/thinking/guard/test", methods=["POST"])
def api_test():
    if _run is None: return jsonify({"ok": False, "error":"guard_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_run(str(d.get("name","")), dict(d.get("args") or {})))
# c=a+b