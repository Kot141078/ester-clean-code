# -*- coding: utf-8 -*-
"""routes/finance_routes.py - REST/UI dlya modul "Puti k dokhodu".

Ruchki:
  GET /fin/probe
  POST /fin/evaluate {"text":"...", "target_amount":1000, "timeframe_days":14}
  POST /fin/roadmap {"text":"...", "target_amount":1000, "timeframe_days":14}
  POST /fin/create_play {"text":"...", "mode":"A|B"}
  GET /admin/fin

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.finance import pathways as FP
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("finance_routes", __name__, url_prefix="/fin")

@bp.route("/probe", methods=["GET"])
def probe():
    return jsonify(FP.probe())

@bp.route("/evaluate", methods=["POST"])
def evaluate():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify(FP.evaluate(d.get("text",""), float(d.get("target_amount",1000.0)), int(d.get("timeframe_days",14))))

@bp.route("/roadmap", methods=["POST"])
def roadmap():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify(FP.make_roadmap(d.get("text",""), float(d.get("target_amount",1000.0)), int(d.get("timeframe_days",14))))

@bp.route("/create_play", methods=["POST"])
def create_play():
    d=request.get_json(force=True, silent=True) or {}
    return jsonify(FP.create_and_play(d.get("text",""), d.get("mode")))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_finance.html")

def register(app):
    app.register_blueprint(bp)