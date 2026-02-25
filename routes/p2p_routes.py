# -*- coding: utf-8 -*-
"""routes/p2p_routes.py - REST: P2P bloom-filtr (status/add/export/merge/reset/from_passport).

Mosty:
- Yavnyy: (Veb ↔ P2P) kompaktnyy obmen “what uzhe videl.”
- Skrytyy #1: (Profile ↔ Audit) operatsii filtra shtampuyutsya.
- Skrytyy #2: (Discover/Cron ↔ Avtonomiya) legko vstraivaetsya v nochnye protsedury i avto-registratsiyu.

Zemnoy abzats:
Legkiy protokol “ne povtoryatsya”: vmesto spiskov id gonyaem paru soten bayt s bitami.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("p2p_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.p2p.bloom import status as _st, add as _add, export as _exp, merge as _merge, reset as _reset, from_passport as _fromp  # type: ignore
except Exception:
    _st=_add=_exp=_merge=_reset=_fromp=None  # type: ignore

@bp.route("/p2p/bloom/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error":"p2p_unavailable"}), 500
    return jsonify(_st())

@bp.route("/p2p/bloom/add", methods=["POST"])
def api_add():
    if _add is None: return jsonify({"ok": False, "error":"p2p_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_add(list(d.get("ids") or [])))

@bp.route("/p2p/bloom/export", methods=["GET"])
def api_export():
    if _exp is None: return jsonify({"ok": False, "error":"p2p_unavailable"}), 500
    return jsonify(_exp())

@bp.route("/p2p/bloom/merge", methods=["POST"])
def api_merge():
    if _merge is None: return jsonify({"ok": False, "error":"p2p_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_merge(int(d.get("m",0)), int(d.get("k",0)), str(d.get("bits_hex",""))))

@bp.route("/p2p/bloom/reset", methods=["POST"])
def api_reset():
    if _reset is None: return jsonify({"ok": False, "error":"p2p_unavailable"}), 500
    return jsonify(_reset())

@bp.route("/p2p/bloom/from_passport", methods=["POST"])
def api_from_passport():
    if _fromp is None: return jsonify({"ok": False, "error":"p2p_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_fromp(int(d.get("limit",5000))))
# c=a+b