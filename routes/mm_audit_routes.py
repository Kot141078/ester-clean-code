# -*- coding: utf-8 -*-
"""
routes/mm_audit_routes.py - REST: audit obkhodov get_mm().

Mosty:
- Yavnyy: (Veb ↔ Linter) zapuskaem skan i smotrim posledniy otchet.
- Skrytyy #1: (Memory ↔ Profile) modul uzhe pishet profile.
- Skrytyy #2: (RBAC ↔ Kontrol) skan - dlya operator/admin, otchet - vsem.

Zemnoy abzats:
Knopka «proverit fabriku pamyati»: bystro ponimaem, gde kod obkhodit obschiy put.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mm_audit_routes", __name__)

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
    from modules.quality.mm_audit import scan as _scan, last_report as _last  # type: ignore
except Exception:
    _scan=_last=None  # type: ignore

@bp.route("/quality/mm_audit/scan", methods=["POST"])
def api_scan():
    if _scan is None: return jsonify({"ok": False, "error":"audit_unavailable"}), 500
    if not _rbac_ok(["operator","admin"]): return jsonify({"ok": False, "error":"forbidden"}), 403
    d=request.get_json(True, True) or {}
    return jsonify(_scan(list(d.get("masks") or [])))

@bp.route("/quality/mm_audit/report", methods=["GET"])
def api_report():
    if _last is None: return jsonify({"ok": False, "error":"audit_unavailable"}), 500
    return jsonify(_last())
# c=a+b