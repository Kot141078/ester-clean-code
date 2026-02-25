# -*- coding: utf-8 -*-
"""routes/data_govern_routes.py - REST dlya klassov dannykh/retenshna/zabveniya.

Mosty:
- Yavnyy: (Veb ↔ Politika dannykh) yavnye ruchki dlya klassifikatsii i srokov khraneniya.
- Skrytyy #1: (Audit ↔ Prozrachnost) otchety JSON, legko podklyuchit v nightly.
- Skrytyy #2: (Memory ↔ Bezopasnost) uvazhaet DG_PROTECT_TAGS.

Zemnoy abzats:
Polozhili yarlyk - poluchili srok. By request - zabyli.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_dg = Blueprint("data_govern", __name__)

try:
    from modules.data.govern import classify as _classify, retention_sweep as _sweep, request_erase as _erase  # type: ignore
except Exception:
    _classify = _sweep = _erase = None  # type: ignore

def register(app):
    app.register_blueprint(bp_dg)

@bp_dg.route("/data/classify", methods=["POST"])
def api_classify():
    if _classify is None: return jsonify({"ok": False, "error":"data govern unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_classify(str(d.get("query","")), list(d.get("add_tags") or []), d.get("class")))

@bp_dg.route("/data/retention/sweep", methods=["POST"])
def api_sweep():
    if _sweep is None: return jsonify({"ok": False, "error":"data govern unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_sweep(bool(d.get("dry_run", False))))

@bp_dg.route("/data/request/erase", methods=["POST"])
def api_erase():
    if _erase is None: return jsonify({"ok": False, "error":"data govern unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_erase(list(d.get("keys") or [])))
# c=a+b