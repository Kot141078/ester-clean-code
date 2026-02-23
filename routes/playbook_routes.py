# -*- coding: utf-8 -*-
"""
routes/playbook_routes.py - REST: validatsiya/zapusk/spisok pleybukov.

Mosty:
- Yavnyy: (Veb ↔ Kaskady) interfeys dlya stsenariev.
- Skrytyy #1: (Ekonomika ↔ Ogranicheniya) uvazhaet CostFence.
- Skrytyy #2: (UX ↔ Panel) druzhit s panelyu.

Zemnoy abzats:
Stsenarii stanovyatsya knopkami.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_pb = Blueprint("playbook_routes", __name__)

try:
    from modules.playbooks.runner import _parse as _parse, validate as _validate, run as _run, PLAYBOOKS_DIR  # type: ignore
except Exception:
    _parse=_validate=_run=None  # type: ignore
    PLAYBOOKS_DIR="data/playbooks"

def register(app):
    app.register_blueprint(bp_pb)

@bp_pb.route("/playbooks/run", methods=["POST"])
def api_run():
    if None in (_parse,_validate,_run): return jsonify({"ok": False, "error":"playbooks_unavailable"}), 500
    data = request.get_data(as_text=True) or "{}"
    obj = _parse(data, request.headers.get("Content-Type",""))
    v = _validate(obj)
    if not v.get("ok"): return jsonify({"ok": False, "error":"invalid_playbook", "validate": v})
    return jsonify(_run(obj))

@bp_pb.route("/playbooks/validate", methods=["POST"])
def api_val():
    if _parse is None or _validate is None: return jsonify({"ok": False, "error":"playbooks_unavailable"}), 500
    data = request.get_data(as_text=True) or "{}"
    obj = _parse(data, request.headers.get("Content-Type",""))
    return jsonify(_validate(obj))

@bp_pb.route("/playbooks/list", methods=["GET"])
def api_list():
    os.makedirs(PLAYBOOKS_DIR, exist_ok=True)
    arr=[]
    for fn in os.listdir(PLAYBOOKS_DIR):
        if fn.endswith((".json",".yaml",".yml")):
            arr.append({"name": fn, "path": os.path.join(PLAYBOOKS_DIR, fn)})
    return jsonify({"ok": True, "items": arr})
# c=a+b