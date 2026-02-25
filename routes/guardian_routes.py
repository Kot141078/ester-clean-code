# -*- coding: utf-8 -*-
"""routes/guardian_routes.py - REST: doverennye kontakty i podgotovka eskalatsii.

Mosty:
- Yavnyy: (Veb ↔ Zabota) UI/volya upravlyayut kontaktami i poluchayut instruktsii pri ChS.
- Skrytyy #1: (LegalGuard ↔ Ostorozhnost) mozhno predvaritelno proveryat stsenariy.
- Skrytyy #2: (Profile ↔ Audit) operatsii fiksiruyutsya khukom.

Zemnoy abzats:
Nuzhna pomosch - i vse pod rukoy: komu, kak i chto say; pri etom nikakikh “skrytykh zvonkov” - just podskazki.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("guardian_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.guardian.contacts import upsert_contact as _up, list_contacts as _ls, prepare_escalation as _prep  # type: ignore
except Exception:
    _up=_ls=_prep=None  # type: ignore

@bp.route("/guardian/contact/upsert", methods=["POST"])
def api_upsert():
    if _up is None: return jsonify({"ok": False, "error":"guardian_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_up(d))

@bp.route("/guardian/contact/list", methods=["GET"])
def api_list():
    if _ls is None: return jsonify({"ok": False, "error":"guardian_unavailable"}), 500
    return jsonify(_ls())

@bp.route("/guardian/escalate/prepare", methods=["POST"])
def api_prepare():
    if _prep is None: return jsonify({"ok": False, "error":"guardian_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_prep(str(d.get("kind","emergency")), str(d.get("who","")), str(d.get("message",""))))
# c=a+b