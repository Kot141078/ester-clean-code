# -*- coding: utf-8 -*-
"""routes/error_heatmap_routes.py - REST/UI dlya error-heatmap.

Ruchki:
  POST /error/heatmap/build {"n":300}
  GET /admin/error_heatmap

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.vision.error_heatmap import build
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("error_heatmap_routes", __name__, url_prefix="/error/heatmap")

@bp.route("/build", methods=["POST"])
def b():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(build(int(data.get("n", 300))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_error_heatmap.html")

def register(app):
    app.register_blueprint(bp)