# -*- coding: utf-8 -*-
"""routes/discovery_routes.py - REST-pult avtopodkhvata: scan/register/status/autorun.

Mosty:
- Yavnyy: (Web ↔ Bootstrap) handy upravlenie poiskom i podklyucheniem moduley.
- Skrytyy #1: (Passport ↔ Prozrachnost) vse sobytiya v zhurnale.
- Skrytyy #2: (CapMap/Hub ↔ UI) udobnye JSON/HTML dlya paneley.

Zemnoy abzats:
Eto remote “Set/Pusk”: nashel - podklyuchil - proveril, bez redaktirovaniya app.py.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("discovery_routes", __name__)

def register(app):
    app.register_blueprint(bp)
    try:
        from modules.discovery.loader import attach_app  # type: ignore
        attach_app(app)
    except Exception:
        pass

try:
    from modules.discovery.loader import scan as _scan, register as _reg, status as _st, autorun as _auto  # type: ignore
except Exception:
    _scan=_reg=_st=_auto=None  # type: ignore

@bp.route("/app/discover/scan", methods=["GET"])
def api_scan():
    if _scan is None: return jsonify({"ok": False, "error":"discover_unavailable"}), 500
    return jsonify(_scan())

@bp.route("/app/discover/register", methods=["POST"])
def api_register():
    if _reg is None: return jsonify({"ok": False, "error":"discover_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_reg(list(d.get("modules") or [])))

@bp.route("/app/discover/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error":"discover_unavailable"}), 500
    return jsonify(_st())

@bp.route("/app/discover/autorun", methods=["POST"])
def api_autorun():
    if _auto is None: return jsonify({"ok": False, "error":"discover_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_auto(d.get("enable"), d.get("interval_sec")))
# c=a+b