# -*- coding: utf-8 -*-
"""
routes/cron_nightly_routes.py - REST: status i ruchnoy zapusk Nightly.

Mosty:
- Yavnyy: (Veb ↔ Cron) zapusk i monitoring tekhprotsedur.
- Skrytyy #1: (Profile ↔ Trassirovka) vse fiksiruetsya.
- Skrytyy #2: (Survival ↔ Rezerv) snapshoty popadayut v bandly.

Zemnoy abzats:
Otkryl panel - nazhal knopku - obsluzhivanie proshlo. Tak i dolzhno byt.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("cron_nightly_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.cron.nightly import run as _run, status as _status  # type: ignore
except Exception:
    _run=_status=None  # type: ignore

@bp.route("/cron/nightly/status", methods=["GET"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"nightly_unavailable"}), 500
    return jsonify(_status())

@bp.route("/cron/nightly/run", methods=["POST"])
def api_run():
    if _run is None: return jsonify({"ok": False, "error":"nightly_unavailable"}), 500
    return jsonify(_run())
# c=a+b