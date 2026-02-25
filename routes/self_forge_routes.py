# -*- coding: utf-8 -*-
"""routes/self_forge_routes.py - REST: dry-run i apply dlya samofordzha.

Mosty:
- Yavnyy: (Veb ↔ Samoizmenenie) dostup k ostorozhnoy zapisi faylov.
- Skrytyy #1: (CautionNet ↔ Bezopasnost) fakticheskaya zapis zaschischena “pilyuley”.
- Skrytyy #2: (Ekonomika ↔ Uchet) zdes mozhno v buduschem vnosit operatsii v ledger.

Zemnoy abzats:
Snachala primerili, potom - zapisali (esli soznatelno podtverdili).

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_forge = Blueprint("self_forge", __name__)

try:
    from modules.self.forge import dry_run as _dry, apply as _apply  # type: ignore
except Exception:
    _dry=_apply=None  # type: ignore

def register(app):
    app.register_blueprint(bp_forge)

@bp_forge.route("/self/forge/dry_run", methods=["POST"])
def api_dry():
    if _dry is None: return jsonify({"ok": False, "error":"forge_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_dry(list(d.get("changes") or [])))

@bp_forge.route("/self/forge/apply", methods=["POST"])
def api_apply():
    if _apply is None: return jsonify({"ok": False, "error":"forge_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_apply(list(d.get("changes") or [])))
# c=a+b