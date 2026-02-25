# -*- coding: utf-8 -*-
"""rutes/guide_ffmpeg_rutes.po - export of MPCh+TC (locally).

Handles:
  POST /guide/ffmpeg/make ZZF0Z -> ZZF1ZZ

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.export.guide_ffmpeg import make
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("guide_ffmpeg_routes", __name__, url_prefix="/guide/ffmpeg")

@bp.route("/make", methods=["POST"])
def mk():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(make((data.get("name") or "guide"), (data.get("text") or "")))

def register(app):
    app.register_blueprint(bp)