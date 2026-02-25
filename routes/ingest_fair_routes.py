# -*- coding: utf-8 -*-
"""routes/ingest_fair_routes.py - REST-panel dlya fairness.

Mosty:
- Yavnyy: (Veb ↔ Inzhest) status i nastroyka kvot.
- Skrytyy #1: (Audit ↔ Control) ruchnaya otmetka rezultatov.
- Skrytyy #2: (Operatsii ↔ Nablyudaemost) udobno dlya UI/skriptov.

Zemnoy abzats:
Krutilka “skolko v minutu” dlya kazhdogo istochnika.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ingest = Blueprint("ingest_fair_routes", __name__)

try:
    from modules.ingest.fair import status as _status, set_quota as _set, mark_result as _mark  # type: ignore
except Exception:
    _status = _set = _mark = None  # type: ignore

def register(app):
    app.register_blueprint(bp_ingest)

@bp_ingest.route("/ingest/fair/status", methods=["GET"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"ingest fairness unavailable"}), 500
    return jsonify(_status())

@bp_ingest.route("/ingest/fair/config", methods=["POST"])
def api_config():
    if _set is None: return jsonify({"ok": False, "error":"ingest fairness unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_set(str(d.get("source","default")), float(d.get("rps",1.0)), int(d.get("burst",2))))

@bp_ingest.route("/ingest/fair/mark", methods=["POST"])
def api_mark():
    if _mark is None: return jsonify({"ok": False, "error":"ingest fairness unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_mark(str(d.get("source","default")), int(d.get("code",200))))
# c=a+b