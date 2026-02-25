# -*- coding: utf-8 -*-
"""routes/coach_routes.py - REST/UI dlya kouchinga myshleniya.

Ruchki:
  GET /thinking/coach/status
  POST /thinking/coach/diagnosis {"window":200}
  POST /thinking/coach/suggest {"k":5}
  POST /thinking/coach/commit_goal {"text":"..."}
  POST /thinking/coach/retro {"window":400}
  GET /admin/coach

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.thinking import coach as CO
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("coach_routes", __name__, url_prefix="/thinking/coach")

@bp.route("/status", methods=["GET"])
def status():
    return jsonify(CO.status())

@bp.route("/diagnose", methods=["POST"])
def diagnose():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(CO.diagnose(int(d.get("window",200))))

@bp.route("/suggest", methods=["POST"])
def suggest():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(CO.suggest_micro_goals(int(d.get("k",5))))

@bp.route("/commit_goal", methods=["POST"])
def commit_goal():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(CO.commit_micro_goal(d.get("text","")))

@bp.route("/retro", methods=["POST"])
def retro():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(CO.retro(int(d.get("window",400))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_coach.html")

def register(app):
    app.register_blueprint(bp)