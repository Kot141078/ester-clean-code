# -*- coding: utf-8 -*-
"""routes/thinking_rules_routes.py - REST: list/set/evaluate rules "voli".

Mosty:
- Yavnyy: (Veb ↔ Volya) upravlyaem pravilami i vruchnuyu zapuskaem ikh.
- Skrytyy #1: (Profile ↔ Prozrachnost) vse izmeneniya i progon fiksiruyutsya.
- Skrytyy #2: (Cron/Watch ↔ Avtonomiya) legko privyazyvaetsya k /watch/scan i /cron/tick.

Zemnoy abzats:
Panel “esli-to”: zapishi pravila - ispolnyay po sobytiyu iz watch/cron or vruchnuyu.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("thinking_rules_routes", __name__)

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
    from modules.thinking.rules_engine import list_rules as _list, set_rules as _set, evaluate as _eval  # type: ignore
except Exception:
    _list=_set=_eval=None  # type: ignore

@bp.route("/thinking/rules/list", methods=["GET"])
def api_list():
    if _list is None: return jsonify({"ok": False, "error":"rules_unavailable"}), 500
    return jsonify(_list())

@bp.route("/thinking/rules/set", methods=["POST"])
def api_set():
    if _set is None: return jsonify({"ok": False, "error":"rules_unavailable"}), 500
    if not _rbac_write_ok(): return jsonify({"ok": False, "error":"forbidden"}), 403
    d=request.get_json(True, True) or {}
    return jsonify(_set(list(d.get("rules") or [])))

@bp.route("/thinking/rules/evaluate", methods=["POST"])
def api_evaluate():
    if _eval is None: return jsonify({"ok": False, "error":"rules_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_eval(dict(d.get("context") or {})))
# c=a+b