# -*- coding: utf-8 -*-
"""
routes/mass_tuner_weighted_routes.py - REST/UI dlya vzveshennogo tyuninga.

Ruchki:
  POST /mass_weighted/preview {"radius":80,"penalty":0.05,"min_thr":0.82,"lang":"eng+rus","use_scale":true}
  POST /mass_weighted/apply   {...}
  GET  /admin/mass_weighted

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.triggers.mass_tuner_weighted import preview, apply
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mass_tuner_weighted_routes", __name__, url_prefix="/mass_weighted")

@bp.route("/preview", methods=["POST"])
def prev():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(preview(data))

@bp.route("/apply", methods=["POST"])
def app():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(apply(data))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_mass_weighted.html")

def register(app):
    app.register_blueprint(bp)