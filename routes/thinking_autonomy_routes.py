# -*- coding: utf-8 -*-
"""routes/thinking_autonomy_routes.py - REST/UI dlya proaktivnogo myshleniya.

Ruchki:
  GET /thinking/autonomy/status
  POST /thinking/autonomy/enable
  POST /thinking/autonomy/disable
  POST /thinking/autonomy/run_trigger {"name":"...", "goal":"...", "params":{...}}
  POST /thinking/autonomy/test_cascade {"goal":"demo goal"} # bystryy test kaskada
  GET /admin/thinking_autonomy

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.thinking import proactive, cascade
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("thinking_autonomy_routes", __name__, url_prefix="/thinking/autonomy")

@bp.route("/status", methods=["GET"])
def status():
    return jsonify(proactive.status())

@bp.route("/enable", methods=["POST"])
def enable():
    return jsonify(proactive.enable())

@bp.route("/disable", methods=["POST"])
def disable():
    return jsonify(proactive.disable())

@bp.route("/run_trigger", methods=["POST"])
def run_trigger():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(proactive.run_trigger(d.get("name","manual"), d))

@bp.route("/test_cascade", methods=["POST"])
def test_cascade():
    d=request.get_json(force=True,silent=True) or {}
    goal=d.get("goal","otkryt bloknot, napisat i sokhranit")
    out=cascade.run_cascade(goal, {"params":{"objective":goal}})
    return jsonify(out)

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_thinking_autonomy.html")

def register(app):
    app.register_blueprint(bp)