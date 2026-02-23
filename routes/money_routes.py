# -*- coding: utf-8 -*-
"""
routes/money_routes.py - REST/UI dlya orkestratora «mne nuzhny dengi».

Ruchki:
  GET  /money/probe
  POST /money/trigger_check     {"text":"Ester, mne nuzhny dengi"}
  GET  /money/questions
  POST /money/profile           {"answers":{...}}
  POST /money/strategies        {"answers":{...},"target_amount":1000,"timeframe_days":14}
  POST /money/judge             {"answers":{...}}
  POST /money/garage            {"answers":{...}}
  POST /money/run               {"answers":{...},"target_amount":1000,"timeframe_days":14,"mode":"A|B"}

  GET  /admin/money

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.money import orchestrator as MO
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("money_routes", __name__, url_prefix="/money")

@bp.route("/probe", methods=["GET"])
def probe():
    return jsonify(MO.probe())

@bp.route("/trigger_check", methods=["POST"])
def trigger_check():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify({"ok":True,"match": MO.match_trigger(d.get("text",""))})

@bp.route("/questions", methods=["GET"])
def questions():
    return jsonify(MO.start_questionnaire())

@bp.route("/profile", methods=["POST"])
def profile():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(MO.build_profile(d.get("answers") or {}))

@bp.route("/strategies", methods=["POST"])
def strategies():
    d=request.get_json(force=True,silent=True) or {}
    pr=MO.build_profile(d.get("answers") or {})
    return jsonify(MO.gather_strategies(pr.get("profile") or {}, float(d.get("target_amount",1000.0)), int(d.get("timeframe_days",14))))

@bp.route("/judge", methods=["POST"])
def judge():
    d=request.get_json(force=True,silent=True) or {}
    pr=MO.build_profile(d.get("answers") or {})
    st=MO.gather_strategies(pr.get("profile") or {})
    return jsonify(MO.consult_judge(st.get("items") or []))

@bp.route("/garage", methods=["POST"])
def garage():
    d=request.get_json(force=True,silent=True) or {}
    pr=MO.build_profile(d.get("answers") or {})
    st=MO.gather_strategies(pr.get("profile") or {})
    return jsonify(MO.propose_garage_build(pr.get("profile") or {}, st.get("items") or []))

@bp.route("/run", methods=["POST"])
def run():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(MO.master_run(
        d.get("answers") or {},
        float(d.get("target_amount",1000.0)),
        int(d.get("timeframe_days",14)),
        d.get("mode")
    ))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_money.html")

def register(app):
    app.register_blueprint(bp)