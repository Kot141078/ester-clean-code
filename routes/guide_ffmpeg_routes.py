# -*- coding: utf-8 -*-
"""
routes/guide_ffmpeg_routes.py - eksport MP4+TTS (lokalno).

Ruchki:
  POST /guide/ffmpeg/make {"name":"guide_demo","text":"Shag odin..."} -> {folder, scripts, voice:bool}

# c=a+b
"""
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