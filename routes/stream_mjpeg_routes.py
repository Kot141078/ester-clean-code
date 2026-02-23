# -*- coding: utf-8 -*-
"""
routes/stream_mjpeg_routes.py - REST+UI dlya MJPEG.

Ruchki:
  GET  /stream/screen?fps=8      - potok
  GET  /admin/stream             - panel

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, Response, request, render_template
from modules.stream.screen_mjpeg import stream_generator, BOUNDARY
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("stream_mjpeg_routes", __name__, url_prefix="/stream")

@bp.route("/screen", methods=["GET"])
def screen():
    fps = int(request.args.get("fps", 8))
    gen = stream_generator(fps=fps)
    return Response(gen, mimetype=f"multipart/x-mixed-replace; boundary={BOUNDARY}")

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_stream.html")

def register(app):
    app.register_blueprint(bp)