# -*- coding: utf-8 -*-
"""
routes/memory_summary_routes.py - REST/UI svodok pamyati.

Ruchki:
  GET  /memory/summary/list
  POST /memory/summary/generate {"mode":"day|week|month"}
  GET  /memory/summary/get?id=...
  POST /memory/summary/cleanup
  GET  /admin/memory_summary

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.memory import summary
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("memory_summary_routes", __name__, url_prefix="/memory/summary")

@bp.route("/list", methods=["GET"])
def list_():
    return jsonify(summary.list_summaries())

@bp.route("/generate", methods=["POST","GET"])
def generate():
    mode = request.args.get("mode") or (request.get_json(silent=True) or {}).get("mode","day")
    return jsonify(summary.generate_summary(mode))

@bp.route("/get", methods=["GET"])
def get_():
    sid=request.args.get("id")
    return jsonify(summary.get_summary(sid))

@bp.route("/cleanup", methods=["POST"])
def cleanup():
    d=request.get_json(silent=True,force=True) or {}
    return jsonify(summary.cleanup_old(int(d.get("limit",100))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_memory_summary.html")

def register(app):
    app.register_blueprint(bp)