# -*- coding: utf-8 -*-
"""
routes/context_inspector_routes.py - REST/UI dlya inspektora konteksta.

Ruchki:
  POST /context/heatmap/build {"n":200}
  GET  /admin/context

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.vision.context_inspector import build
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("context_inspector_routes", __name__, url_prefix="/context")

@bp.route("/heatmap/build", methods=["POST"])
def heatmap():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(build(int(data.get("n", 200))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_context.html")

def register(app):
    app.register_blueprint(bp)