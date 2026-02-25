# -*- coding: utf-8 -*-
"""routes/smoke_routes.py - REST: /tools/smoke/* - progon/status/spisok tests.

Mosty:
- Yavnyy: (Veb ↔ Diagnostika) knopki zapustit smoke, posmotret otchet.
- Skrytyy #1: (Cron/Hub ↔ Avtonomiya) goditsya dlya nochnykh progona i dlya paneli.
- Skrytyy #2: (Passport ↔ Prozrachnost) sobytiya protokoliruyutsya.

Zemnoy abzats:
Odin POST - i sistema probegaetsya po klyuchevym tochkam, davaya zelenuyu/krasnuyu lampu.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("smoke_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.diagnostics.smoke_runner import run as _run, status as _st, list_tests as _lt  # type: ignore
except Exception:
    _run=_st=_lt=None  # type: ignore

@bp.route("/tools/smoke/run", methods=["POST"])
def api_run():
    if _run is None: return jsonify({"ok": False, "error":"smoke_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_run(bool(d.get("fast", False))))

@bp.route("/tools/smoke/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error":"smoke_unavailable"}), 500
    return jsonify(_st())

@bp.route("/tools/smoke/tests", methods=["GET"])
def api_tests():
    if _lt is None: return jsonify({"ok": False, "error":"smoke_unavailable"}), 500
    return jsonify(_lt())
# c=a+b