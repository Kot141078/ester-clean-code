# -*- coding: utf-8 -*-
"""routes/watch_routes.py - REST: status/konfig/scanner papok bez demonov.

Mosty:
- Yavnyy: (Veb ↔ FS) skaniruem vkhodyaschie i formiruem sobytiya dlya pravil.
- Skrytyy #1: (Profile ↔ Prozrachnost) fiksatsiya konfigov/skanov.
- Skrytyy #2: (Thinking Rules ↔ Avtonomiya) obedinenie s evaluate().

Zemnoy abzats:
Odin POST - i “pochtovyy yaschik” razobran; novoe otpravleno dalshe po konveyeru.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("watch_routes", __name__)

def register(app):
    app.register_blueprint(bp)

def _rbac_write_ok():
    if (os.getenv("RBAC_REQUIRED","true").lower()=="false"): return True
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(["admin","operator"])
    except Exception:
        return True

try:
    from modules.watch.folder_scanner import status as _st, set_config as _cfg, scan as _scan  # type: ignore
except Exception:
    _st=_cfg=_scan=None  # type: ignore

@bp.route("/watch/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error":"watch_unavailable"}), 500
    return jsonify(_st())

@bp.route("/watch/config/set", methods=["POST"])
def api_config_set():
    if _cfg is None: return jsonify({"ok": False, "error":"watch_unavailable"}), 500
    if not _rbac_write_ok(): return jsonify({"ok": False, "error":"forbidden"}), 403
    d=request.get_json(True, True) or {}
    return jsonify(_cfg(list(d.get("dirs") or []), list(d.get("patterns") or [])))

@bp.route("/watch/scan", methods=["POST"])
def api_scan():
    if _scan is None: return jsonify({"ok": False, "error":"watch_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_scan(bool(d.get("autoprocess", True))))
# c=a+b