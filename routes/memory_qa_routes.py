# -*- coding: utf-8 -*-
"""
routes/memory_qa_routes.py - REST/UI dlya QA pamyati.

Ruchki:
  GET  /memory/qa/summary
  POST /memory/qa/run {"auto_fix":true|false}
  GET  /admin/memory_qa

# c=a+b
"""
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