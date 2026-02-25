# -*- coding: utf-8 -*-
"""routes/retire_routes.py - REST/UI dlya dolgosrochnogo planirovschika.

Ruchki:
  GET /retire/probe
  GET /retire/profile
  POST /retire/save_profile { ...polya... }
  POST /retire/simulate {"months":120}
  GET /retire/month_plan
  POST /retire/month_run {"mode":"A|B"}
  GET /retire/report
  GET /admin/retire

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.retire import planner as RP
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("retire_routes", __name__, url_prefix="/retire")

@bp.route("/probe", methods=["GET"])
def probe():
    return jsonify(RP.probe())

@bp.route("/profile", methods=["GET"])
def profile():
    return jsonify(RP.profile())

@bp.route("/save_profile", methods=["POST"])
def save_profile():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(RP.save_profile(d))

@bp.route("/simulate", methods=["POST"])
def simulate():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(RP.simulate(int(d.get("months",120))))

@bp.route("/month_plan", methods=["GET"])
def month_plan():
    return jsonify(RP.make_monthly_plan())

@bp.route("/month_run", methods=["POST"])
def month_run():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(RP.run_month(d.get("mode")))

@bp.route("/report", methods=["GET"])
def report():
    return jsonify(RP.monthly_report())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_retire.html")

def register(app):
    app.register_blueprint(bp)