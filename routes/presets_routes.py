# -*- coding: utf-8 -*-
"""
routes/presets_routes.py - upravlenie presetami makrosov/vorkflou.

Ruchki:
  GET  /presets/list             -> {ok, items:[names]}
  POST /presets/install {"name":"preset_notepad_intro"} -> {ok, workflow}
  POST /presets/install_all      -> {ok, count}

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict
from modules.thinking.macro_presets import list_presets
from modules.thinking.rpa_workflows import save_workflow
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("presets_routes", __name__, url_prefix="/presets")

@bp.route("/list", methods=["GET"])
def lst():
    pres = list_presets()
    return jsonify({"ok": True, "items": list(pres.keys())})

@bp.route("/install", methods=["POST"])
def install():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    pres = list_presets()
    if name not in pres:
        return jsonify({"ok": False, "error": "unknown_preset"}), 404
    wf = pres[name]
    save_workflow(wf["name"], wf)
    return jsonify({"ok": True, "workflow": wf["name"]})

@bp.route("/install_all", methods=["POST"])
def install_all():
    pres = list_presets()
    c = 0
    for wf in pres.values():
        save_workflow(wf["name"], wf)
        c += 1
    return jsonify({"ok": True, "count": c})

def register(app):
    app.register_blueprint(bp)