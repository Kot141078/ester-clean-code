# -*- coding: utf-8 -*-
"""routes/macro_learn_routes.py - REST/UI dlya obucheniya iz makrosov.

Ruchki:
  GET /macro_learn/preview
  POST /macro_learn/export
  POST /macro_learn/apply
  GET /admin/macro_learn

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.learn.from_macro import preview, export, apply
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("macro_learn_routes", __name__, url_prefix="/macro_learn")

@bp.route("/preview", methods=["GET"])
def p(): return jsonify(preview())

@bp.route("/export", methods=["POST"])
def e(): return jsonify(export())

@bp.route("/apply", methods=["POST"])
def a(): return jsonify(apply())

@bp.route("/admin", methods=["GET"])
def admin(): return render_template("admin_macro_learn.html")

def register(app):
    app.register_blueprint(bp)