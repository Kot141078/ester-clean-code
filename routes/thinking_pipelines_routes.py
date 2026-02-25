# -*- coding: utf-8 -*-
"""routes/thinking_pipelines_routes.py - REST/UI dlya myslitelnykh payplaynov.

Ruchki:
  GET /thinking/pipelines/builtins
  POST /thinking/pipelines/run { "name": "...", "goal": "...", "params": {...} }
  GET /admin/thinking_pipelines

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.thinking import pipelines as TP
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("thinking_pipelines_routes", __name__, url_prefix="/thinking/pipelines")

@bp.route("/builtins", methods=["GET"])
def builtins():
    return jsonify({"ok":True,"items":TP.builtins()})

@bp.route("/run", methods=["POST"])
def run():
    d = request.get_json(force=True, silent=True) or {}
    spec = TP.make_spec(d.get("name","pipeline"), d.get("goal",""), d.get("params") or {})
    out = TP.run_pipeline(spec)
    return jsonify(out)

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_thinking_pipelines.html")

def register(app):
    app.register_blueprint(bp)