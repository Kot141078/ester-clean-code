# -*- coding: utf-8 -*-
"""routes/garage_jobs_routes.py - REST: import/listing/skoring vakansiy.

Mosty:
- Yavnyy: (Veb ↔ Garazh) bystraya priemka i otsenka zadach.
- Skrytyy #1: (Memory ↔ Profile) vse sobytiya logiruyutsya.
- Skrytyy #2: (Volya ↔ Plan) eksheny obraschayutsya k tem zhe funktsiyam.

Zemnoy abzats:
Eto "priemnaya" v garazhe: berem zayavku, kladem v spisok, otsenili - gotovo k rabote.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("garage_jobs_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.garage.jobs import job_import as _import, job_list as _list, job_score as _score  # type: ignore
except Exception:
    _import=_list=_score=None  # type: ignore

@bp.route("/garage/job/import", methods=["POST"])
def api_job_import():
    if _import is None: return jsonify({"ok": False, "error":"garage_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_import(d))

@bp.route("/garage/job/list", methods=["GET"])
def api_job_list():
    if _list is None: return jsonify({"ok": False, "error":"garage_unavailable"}), 500
    return jsonify(_list())

@bp.route("/garage/job/score", methods=["POST"])
def api_job_score():
    if _score is None: return jsonify({"ok": False, "error":"garage_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_score(str(d.get("id",""))))
# c=a+b