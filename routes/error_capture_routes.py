# -*- coding: utf-8 -*-
"""
routes/error_capture_routes.py - REST dlya error-capture.

Ruchki:
  POST /vision/error/report {"kind":"ocr|template","box":{...} | "point":{...}, "why":"..."}

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.vision.error_capture import report
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("error_capture_routes", __name__, url_prefix="/vision/error")

@bp.route("/report", methods=["POST"])
def rep():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(report(str(data.get("kind","")), data))

def register(app):
    app.register_blueprint(bp)