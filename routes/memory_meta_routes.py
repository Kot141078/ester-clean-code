# -*- coding: utf-8 -*-
"""routes/memory_meta_routes.py - REST/UI dlya meta-pamyati.

Ruchki:
  POST /memory/meta/evaluate
  POST /memory/meta/decay
  POST /memory/meta/consolidate
  GET /memory/meta/stats
  GET /admin/memory_meta

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, render_template, request
from modules.memory import meta
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("memory_meta_routes", __name__, url_prefix="/memory/meta")

@bp.route("/evaluate", methods=["POST"])
def evaluate():
    return jsonify(meta.evaluate_significance())

@bp.route("/decay", methods=["POST"])
def decay():
    return jsonify(meta.decay_forget())

@bp.route("/consolidate", methods=["POST"])
def consolidate():
    return jsonify(meta.consolidate())

@bp.route("/stats", methods=["GET"])
def stats():
    return jsonify(meta.stats())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_memory_meta.html")

def register(app):
    app.register_blueprint(bp)