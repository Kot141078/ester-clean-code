# -*- coding: utf-8 -*-
"""routes/security_rbac_routes.py - REST: /security/rbac/* i podklyuchenie guard'a.

Mosty:
- Yavnyy: (Veb ↔ RBAC) status/config i podklyuchenie k Flask lifecycle.
- Skrytyy #1: (Passport ↔ Audit) pravki pravil fiksiruyutsya.
- Skrytyy #2: (Policy ↔ Upravlenie) menyaem roli bez restartov.

Zemnoy abzats:
Vklyuchili - i u riskovannykh ruchek poyavilsya “okhrannik” na vkhode.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("security_rbac_routes", __name__)

def register(app):
    app.register_blueprint(bp)
    try:
        from modules.security.rbac import guard as _guard  # type: ignore
        _guard(app)
    except Exception:
        pass

try:
    from modules.security.rbac import status as _st, config as _cfg  # type: ignore
except Exception:
    _st=_cfg=None  # type: ignore

@bp.route("/security/rbac/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error":"rbac_unavailable"}), 500
    return jsonify(_st())

@bp.route("/security/rbac/config", methods=["POST"])
def api_config():
    if _cfg is None: return jsonify({"ok": False, "error":"rbac_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_cfg(d))
# c=a+b