# -*- coding: utf-8 -*-
"""
routes/action_safety_routes.py - REST/UI dlya bezopasnosti deystviy.

Ruchki:
  GET  /thinking/action_safety/config
  POST /thinking/action_safety/config        {enabled?, risk_tol?, cost_budget_daily?}
  GET  /thinking/action_safety/budget
  POST /thinking/action_safety/evaluate      {action, meta}
  POST  /thinking/action_safety/simulate     {action, meta, trials?}
  POST /thinking/action_safety/decide        {action, meta}   # evaluate + commit/consent/deny
  GET  /admin/action_safety

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.thinking import action_safety as AS
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("action_safety_routes", __name__, url_prefix="/thinking/action_safety")

@bp.route("/config", methods=["GET"])
def cfg_get():
    return jsonify(AS.config_get())

@bp.route("/config", methods=["POST"])
def cfg_set():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(AS.config_set(d))

@bp.route("/budget", methods=["GET"])
def budget():
    return jsonify(AS.budget_status())

@bp.route("/evaluate", methods=["POST"])
def eval_():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(AS.evaluate(d.get("action",""), d.get("meta") or {}))

@bp.route("/simulate", methods=["POST"])
def simulate():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(AS.simulate(d.get("action",""), d.get("meta") or {}, int(d.get("trials",50))))

@bp.route("/decide", methods=["POST"])
def decide():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(AS.decide(d.get("action",""), d.get("meta") or {}))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_action_safety.html")

def register(app):
    app.register_blueprint(bp)