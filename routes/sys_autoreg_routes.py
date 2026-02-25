# -*- coding: utf-8 -*-
"""routes/sys_autoreg_routes.py - REST: auto-registratsiya moduley i upravlenie doverennymi kheshami.

Mosty:
- Yavnyy: (Veb ↔ Avtosborka) pozvolyaet Ester samoy podkhvatyvat novye moduli.
- Skrytyy #1: (RBAC ↔ Bezopasnost) whitelist - only admin; autoreg/tick - operator|admin.
- Skrytyy #2: (Memory ↔ Profile) vse klyuchevye deystviya logiruyutsya cherez modul.

Zemnoy abzats:
Nazhal knopku - i sistema akkuratno podklyuchila novye bloki, nepodkhodyaschie - pometila.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
from flask import current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("sys_autoreg_routes", __name__)

def register(app):
    app.register_blueprint(bp)

# RBAC helper
def _rbac_ok(roles):
    if (os.getenv("RBAC_REQUIRED","true").lower()=="false"): return True
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(roles)
    except Exception:
        return True

try:
    from modules.sys.autoreg import tick as _tick  # type: ignore
    from modules.sys.codetrust import status as _ct_status, whitelist_add as _wl_add  # type: ignore
except Exception:
    _tick=_ct_status=_wl_add=None  # type: ignore

@bp.route("/sys/autoreg/tick", methods=["POST"])
def api_autoreg_tick():
    if _tick is None: return jsonify({"ok": False, "error":"autoreg_unavailable"}), 500
    if not _rbac_ok(["operator","admin"]): return jsonify({"ok": False, "error":"forbidden"}), 403
    d=request.get_json(True, True) or {}
    scans = list(d.get("scan") or [])
    return jsonify(_tick(current_app, scans if scans else None))

@bp.route("/sys/codetrust/status", methods=["GET"])
def api_codetrust_status():
    if _ct_status is None: return jsonify({"ok": False, "error":"codetrust_unavailable"}), 500
    return jsonify(_ct_status())

@bp.route("/sys/codetrust/whitelist", methods=["POST"])
def api_codetrust_whitelist():
    if _wl_add is None: return jsonify({"ok": False, "error":"codetrust_unavailable"}), 500
    if not _rbac_ok(["admin"]): return jsonify({"ok": False, "error":"forbidden"}), 403
    d=request.get_json(True, True) or {}
    path=str(d.get("path",""))
    sha = d.get("sha256")
    return jsonify(_wl_add(path, sha))
# c=a+b