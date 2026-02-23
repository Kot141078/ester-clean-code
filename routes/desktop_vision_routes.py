# -*- coding: utf-8 -*-
"""
routes/desktop_vision_routes.py - REST/UI dlya zreniya rabochego stola.

Ruchki:
  GET  /desktop/vision/probe
  GET  /desktop/vision/anchors
  POST /desktop/vision/anchors/add     {"name":"...", "roi":[x,y,w,h], "template":"path?"}
  POST /desktop/vision/anchors/remove  {"name":"..."}
  POST /desktop/vision/detect          {"image_path":"/tmp/ester_screenshot.png","anchor":"ok_button"}
  POST /desktop/vision/add_sample      {}

  GET  /admin/desktop_vision

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.agents import desktop_vision as DV
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("desktop_vision_routes", __name__, url_prefix="/desktop/vision")

@bp.route("/probe", methods=["GET"])
def probe():
    return jsonify(DV.probe())

@bp.route("/anchors", methods=["GET"])
def anchors():
    return jsonify(DV.anchors_list())

@bp.route("/anchors/add", methods=["POST"])
def anchors_add():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(DV.anchors_add(d.get("name",""), d.get("roi"), d.get("template")))

@bp.route("/anchors/remove", methods=["POST"])
def anchors_remove():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(DV.anchors_remove(d.get("name","")))

@bp.route("/detect", methods=["POST"])
def detect():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(DV.detect(d.get("image_path","/tmp/ester_screenshot.png"), d.get("anchor","")))

@bp.route("/add_sample", methods=["POST"])
def add_sample():
    return jsonify(DV.add_sample())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_desktop_vision.html")

def register(app):
    app.register_blueprint(bp)