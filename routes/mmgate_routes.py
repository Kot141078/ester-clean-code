# -*- coding: utf-8 -*-
"""routes/mmgate_routes.py - REST: status i lint-skan dlya MM Gate.

Mosty:
- Yavnyy: (Veb ↔ Memory) prozrachnost ispolzovaniya fabriki get_mm().
- Skrytyy #1: (Profile ↔ Trassirovka) skany fiksiruyutsya.
- Skrytyy #2: (Rules/Cron ↔ Kachestvo) mozhno dergat iz nightly.

Zemnoy abzats:
Korotkiy otchet: kto khodit cherez dver, a kto “v okno”. Pomogaet naveti poryadok bez polomok.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("mmgate_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.mem.mmgate import status as _st, scan_sources as _scan  # type: ignore
except Exception:
    _st=_scan=None  # type: ignore

@bp.route("/mem/mmgate/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error":"mmgate_unavailable"}), 500
    return jsonify(_st())

@bp.route("/mem/mmgate/scan", methods=["POST"])
def api_scan():
    if _scan is None: return jsonify({"ok": False, "error":"mmgate_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_scan(list(d.get("roots") or [])))
# c=a+b