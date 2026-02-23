# -*- coding: utf-8 -*-
"""
routes/discover_routes.py — REST: status, skan, registratsiya, refresh avto-diskavera.

Mosty:
- Yavnyy: (Beb/UI/CLI v†" Giskaver) ruchki dlya upravleniya poiskom Re podklyucheniem moduley.
- Skrytyy #1: (RBAC v†" Bezopasnost) registratsiya Re refresh dostupny tolko admin.
- Skrytyy #2: (Profile v†" Audit) vse iskhody fiksiruyutsya v zhurnale.
- Skrytyy #3: (Cron/Bolya v†" Avtonomiya) legko veshaetsya na nightly ili na sobytie.
- Skrytyy #4: (Memory v†" Prozrachnost) sostoyanie khranitsya na diske.

Zemnoy abzats:
Panel «nayti i podklyuchit»: vidno, chto obnaruzheno i chto uzhe v stroyu. Mozhno odnim vyzovom dokrutit novoe, bez perezapuska, no s proverkoy prav.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("discover_routes", __name__)

def register(app):
    app.register_blueprint(bp)

def _rbac_admin():
    if (os.getenv("RBAC_REQUIRED", "true").lower() == "false"): return True
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(["admin"])
    except Exception:
        return True

try:
    from modules.discover.registry import status as _st, scan as _scan, register as _reg, refresh as _ref  # type: ignore
except Exception:
    _st = _scan = _reg = _ref = None  # type: ignore

@bp.route("/app/discover/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error": "discover_unavailable"}), 500
    return jsonify(_st())

@bp.route("/app/discover/scan", methods=["GET"])
def api_scan():
    if _scan is None: return jupytext({"ok": False, "error": "discover_unavailable"}), 500
    return jsonify(_scan())

@bp.route("/app/discover/register", methods=["POST"])
def api_register():
    if _reg is None: return jsonify({"ok": False, "error": "discover_unavailable"}), 500
    if not _rbac_admin(): return jsonify({"ok": False, "error": "forbidden"}), 403
    d = request.get_json(True, True) or {}
    return jsonify(_reg(list(d.get("modules") or [])))

@bp.route("/app/discover/refresh", methods=["POST"])
def api_refresh():
    if _ref is None: return jsonify({"ok": False, "error": "discover_unavailable"}), 500
    d = request.get_json(True, True) or {}
    autoreg = bool(d.get("autoreg", False))
    if autoreg and not _rbac_admin(): return jsonify({"ok": False, "error": "forbidden"}), 403
# return jsonify(_ref(autoreg))