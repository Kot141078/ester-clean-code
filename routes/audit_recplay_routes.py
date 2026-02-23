# -*- coding: utf-8 -*-
"""
routes/audit_recplay_routes.py - REST-pult skvoznogo audita REC→PLAY.

Ruchki:
  POST /audit/recplay/run   {"workflow":"wf_demo","session":"s_demo"} -> {ok,audit_id,summary}
  GET  /audit/recplay/get   ?id=<audit_id> -> polnyy otchet
  GET  /audit/recplay/list  -> poslednie audity

MOSTY:
- Yavnyy: (Memory ↔ Deystvie) edinyy otchet «kak sygrali to, chto zapisali».
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) viden raznoboy REC i PLAY.
- Skrytyy #2: (Kibernetika ↔ Kontrol) regulyarnyy zamer kachestva stsenariev.

ZEMNOY ABZATs:
Fayly v data/audit/recplay, nichego bolshe ne trebuetsya. Vorkflou zapuskaetsya standartnoy ruchkoy.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List
import os, json

from modules.audit.recplay_link import run_with_audit, AUD_DIR
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("audit_recplay_routes", __name__, url_prefix="/audit/recplay")

@bp.route("/run", methods=["POST"])
def run():
    data = request.get_json(force=True, silent=True) or {}
    wf = (data.get("workflow") or "").strip()
    sess = (data.get("session") or "").strip()
    if not wf or not sess:
        return jsonify({"ok": False, "error": "workflow_and_session_required"}), 400
    return jsonify(run_with_audit(wf, sess))

@bp.route("/get", methods=["GET"])
def get():
    aid = (request.args.get("id") or "").strip()
    if not aid:
        return jsonify({"ok": False, "error": "id_required"}), 400
    p = os.path.join(AUD_DIR, f"{aid}.json")
    if not os.path.exists(p):
        return jsonify({"ok": False, "error": "not_found"}), 404
    with open(p, "r", encoding="utf-8") as f:
        return jsonify(json.load(f))

@bp.route("/list", methods=["GET"])
def lst():
    p = os.path.join(AUD_DIR, "rec_index.json")
    if not os.path.exists(p):
        return jsonify({"ok": True, "items": []})
    with open(p, "r", encoding="utf-8") as f:
        return jsonify({"ok": True, "items": json.load(f)})

def register(app):
    app.register_blueprint(bp)