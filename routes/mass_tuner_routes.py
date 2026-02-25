# -*- coding: utf-8 -*-
"""routes/ - REST/UI dlya massovogo tyuninga triggerov.

Ruchki:
  POST /mass_tuner/preview {"lang":"eng+rus","threshold":0.8,"scale_from_calibrate":true}
  POST /mass_tuner/apply {...}
  GET /admin/mass_tuner

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.triggers.mass_tuner import preview, apply
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mass_tuner_routes", __name__, url_prefix="/mass_tuner")

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
    return render_template("admin_mass_tuner.html")

def register(app):
    app.register_blueprint(bp)