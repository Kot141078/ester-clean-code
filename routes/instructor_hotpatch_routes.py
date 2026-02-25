# -*- coding: utf-8 -*-
"""routes/instructor_hotpatch_routes.py - REST/UI dlya goryachego tyuninga v instructor-mode.

Ruchki:
  POST /instructor/hotpatch/preview {"radius":80,"penalty":0.05,"min_thr":0.82,"lang":"eng+rus","use_scale":true}
  POST /instructor/hotpatch/apply {...}
  GET /admin/hotpatch

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.coop.instructor_hotpatch import preview, apply
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("instructor_hotpatch_routes", __name__, url_prefix="/instructor/hotpatch")

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
    return render_template("admin_hotpatch.html")

def register(app):
    app.register_blueprint(bp)