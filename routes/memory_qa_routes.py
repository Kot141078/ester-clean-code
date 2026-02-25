# -*- coding: utf-8 -*-
"""rutes/memory_ka_rutes.po - REST/UI for KA memory.

Handles:
  GET /memory/ka/summary
  POST /memory/ka/run ZZF0Z
  GET /admin/memory_ka

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.memory import qa
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("memory_qa_routes", __name__, url_prefix="/memory/qa")

@bp.route("/summary", methods=["GET"])
def summary():
    return jsonify(qa.summary())

@bp.route("/run", methods=["POST"])
def run():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(qa.run_full_qc(bool(d.get("auto_fix",False))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_memory_qa.html")

def register(app):
    app.register_blueprint(bp)