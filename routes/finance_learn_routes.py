# -*- coding: utf-8 -*-
"""routes/finance_learn_routes.py - REST/UI dlya M33 FinScoreLearn.

Ruchki:
  GET /finlearn/probe
  GET /finlearn/model
  POST /finlearn/reset
  POST /finlearn/submit {"channel":"digital_product","sales":15,"price":9,"visitors":500,"ttfb_days":2}
  POST /finlearn/predict {"channel":"digital_product","feas":38,"market":26,"speed":18,"risk_penalty":2}
  GET /admin/finlearn

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.finance import score_learn as FL
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("finance_learn_routes", __name__, url_prefix="/finlearn")

@bp.route("/probe", methods=["GET"])
def probe():
    return jsonify(FL.probe())

@bp.route("/model", methods=["GET"])
def model():
    return jsonify(FL.model())

@bp.route("/reset", methods=["POST"])
def reset():
    return jsonify(FL.reset())

@bp.route("/submit", methods=["POST"])
def submit():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(FL.submit_outcome(
        d.get("channel","digital_product"),
        int(d.get("sales",0)),
        float(d.get("price",0.0)),
        int(d.get("visitors",0)),
        int(d.get("ttfb_days",7))
    ))

@bp.route("/predict", methods=["POST"])
def predict():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(FL.predict_base(
        d.get("channel","digital_product"),
        int(d.get("feas",30)), int(d.get("market",20)),
        int(d.get("speed",15)), int(d.get("risk_penalty",5))
    ))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_finance_learn.html")

def register(app):
    app.register_blueprint(bp)