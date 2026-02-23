# -*- coding: utf-8 -*-
"""
routes/quarantine_routes.py - REST: priem/skan/vypusk artefaktov v staging + prostaya panel.

Mosty:
- Yavnyy: (Volya ↔ Bezopasnost) chelovek/Ester kladut fayly v karantin i vypuskayut posle skana.
- Skrytyy #1: (Audit ↔ Prozrachnost) log/otchety v data/quarantine/<id>.
- Skrytyy #2: (Samodeploy ↔ Kontrol) vypusk idet cherez deployer.stage (dalshe - tabletka/priglashenie na approve).

Zemnoy abzats:
«Predbannik»: vse novoe prokhodit cherez nego. Inache - ne zanosim.

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, jsonify, request, render_template
import base64, os, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_quar = Blueprint("quarantine", __name__, template_folder="../templates", static_folder="../static")

try:
    from modules.quarantine.storage import ingest as _ingest, rescan as _rescan, release_to_staging as _release  # type: ignore
except Exception:
    _ingest = _rescan = _release = None  # type: ignore

def register(app):
    app.register_blueprint(bp_quar)

@bp_quar.route("/quarantine/ingest", methods=["POST"])
def api_ingest():
    if _ingest is None: return jsonify({"ok": False, "error":"quarantine unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(_ingest(str(d.get("path","")), str(d.get("content_b64","")), d.get("meta") or {}))

@bp_quar.route("/quarantine/scan", methods=["POST"])
def api_scan():
    if _rescan is None: return jsonify({"ok": False, "error":"quarantine unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(_rescan(str(d.get("id",""))))

@bp_quar.route("/quarantine/release", methods=["POST"])
def api_release():
    if _release is None: return jsonify({"ok": False, "error":"quarantine unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    return jsonify(_release(str(d.get("id","")), str(d.get("dest_path","")), str(d.get("reason",""))))

@bp_quar.route("/admin/quarantine", methods=["GET"])
def admin_quarantine():
    return render_template("quarantine_console.html")
# c=a+b