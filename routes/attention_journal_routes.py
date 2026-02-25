# -*- coding: utf-8 -*-
"""routes/attention_journal_routes.py - zhurnal vnimaniya.

Ruchki:
  POST /attention/journal/append {"event":"...","detail":{...}}
  GET /attention/journal/list ?n=200
  GET /attention/journal/dump

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.audit.attention_log import append as aj_append, list_last, dump_all
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("attention_journal_routes", __name__, url_prefix="/attention/journal")

@bp.route("/append", methods=["POST"])
def append():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(aj_append(data.get("event",""), data.get("detail") or {}))

@bp.route("/list", methods=["GET"])
def lst():
    n = int((request.args.get("n") or 200))
    return jsonify({"ok": True, "items": list_last(n)})

@bp.route("/dump", methods=["GET"])
def dump():
    return jsonify({"ok": True, "items": dump_all()})

def register(app):
    app.register_blueprint(bp)