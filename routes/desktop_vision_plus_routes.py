# -*- coding: utf-8 -*-
"""routes/desktop_vision_plus_routes.py - REST UI dlya DesktopVision++.

Ruchki:
  GET /desktop/visionpp/probe
  POST /desktop/visionpp/ocr {"image_path":"/tmp/ester_screenshot.png"}
  POST /desktop/visionpp/find_text {"image_path":"...","key":"OK","regex?":false}
  POST /desktop/visionpp/annotate {"image_path":"...","boxes":[{"box":[x,y,w,h],"label":"..."}]}
  POST /desktop/visionpp/heatmap {"image_path":"...","hits":[[x,y,conf],...]}
  POST /desktop/visionpp/find_and_annot {"image_path":"...","key":"OK"}
  GET /admin/desktop_vision_plus

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.agents import desktop_vision_plus as DVPP
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("desktop_vision_plus_routes", __name__, url_prefix="/desktop/visionpp")

@bp.route("/probe", methods=["GET"])
def probe():
    return jsonify(DVPP.probe())

@bp.route("/ocr", methods=["POST"])
def ocr():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(DVPP.ocr(d.get("image_path","/tmp/ester_screenshot.png")))

@bp.route("/find_text", methods=["POST"])
def find_text():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(DVPP.find_text(d.get("image_path","/tmp/ester_screenshot.png"), d.get("key",""), bool(d.get("regex",False))))

@bp.route("/annotate", methods=["POST"])
def annotate():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(DVPP.annotate(d.get("image_path","/tmp/ester_screenshot.png"), d.get("boxes") or []))

@bp.route("/heatmap", methods=["POST"])
def heatmap():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(DVPP.heatmap(d.get("image_path","/tmp/ester_screenshot.png"), d.get("hits") or []))

@bp.route("/find_and_annot", methods=["POST"])
def find_and_annot():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(DVPP.find_text_and_annotate(d.get("image_path","/tmp/ester_screenshot.png"), d.get("key","")))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_desktop_vision_plus.html")

def register(app):
    app.register_blueprint(bp)