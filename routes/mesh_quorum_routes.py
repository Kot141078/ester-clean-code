# -*- coding: utf-8 -*-
"""
routes/mesh_quorum_routes.py - REST: predlozhit, golosovat, status.

Mosty:
- Yavnyy: (Veb ↔ Kvorum) prozrachnoe upravlenie resheniyami.
- Skrytyy #1: (CautionNet ↔ Spread) pomogaem bezopasnoy seti resheniy.
- Skrytyy #2: (Panel ↔ Operator) viden progress golosov.

Zemnoy abzats:
Pered riskom - sprosili sester; nabrali golosa - idem.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_quorum = Blueprint("mesh_quorum", __name__)

try:
    from modules.mesh.quorum import propose as _pp, vote as _vote, status as _st  # type: ignore
except Exception:
    _pp=_vote=_st=None  # type: ignore

def register(app):
    app.register_blueprint(bp_quorum)

@bp_quorum.route("/mesh/quorum/propose", methods=["POST"])
def api_pp():
    if _pp is None: return jsonify({"ok": False, "error":"quorum_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_pp(str(d.get("id","")), int(d.get("ttl",300)), d.get("payload") or {}))

@bp_quorum.route("/mesh/quorum/vote", methods=["POST"])
def api_vote():
    if _vote is None: return jsonify({"ok": False, "error":"quorum_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_vote(str(d.get("id","")), str(d.get("who","anon")), str(d.get("vote","abstain"))))

@bp_quorum.route("/mesh/quorum/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error":"quorum_unavailable"}), 500
    return jsonify(_st())
# c=a+b