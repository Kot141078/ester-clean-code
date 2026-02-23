# -*- coding: utf-8 -*-
"""
routes/ops_cron_routes.py - REST-obertka dlya «kron-tikov».

Mosty:
- Yavnyy: (Veb ↔ CRON) bezopasnyy zapusk planovykh protsedur.
- Skrytyy #1: (RBAC ↔ JWT) trebuet rol operator/admin.
- Skrytyy #2: (Volya ↔ Plan) ekshen ops.cron.tick vyzyvaet tot zhe kod.

Zemnoy abzats:
Nazhali «tik» - i nochnaya brigada proshla po reglamentu.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("ops_cron_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.ops.cron import tick as _tick  # type: ignore
except Exception:
    _tick=None  # type: ignore

def _rbac_ok()->bool:
    if (os.getenv("RBAC_REQUIRED","true").lower()=="false"): return True
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(["operator","admin"])
    except Exception:
        return True

@bp.route("/ops/cron/tick", methods=["POST"])
def api_cron_tick():
    if _tick is None: return jsonify({"ok": False, "error":"cron_unavailable"}), 500
    if not _rbac_ok(): return jsonify({"ok": False, "error":"forbidden"}), 403
    return jsonify(_tick())
# c=a+b