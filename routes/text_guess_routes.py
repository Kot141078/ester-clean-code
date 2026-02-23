# -*- coding: utf-8 -*-
"""
routes/text_guess_routes.py - REST/UI «ugadyvatelya» teksta dlya OCR.

Ruchki:
  POST /text_guess/guess {"events":[...], "window_ms":1200}
  GET  /admin/text_guess

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.replay.text_guess import guess
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("text_guess_routes", __name__, url_prefix="/text_guess")

@bp.route("/guess", methods=["POST"])
def g():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(guess(list(d.get("events") or []), int(d.get("window_ms",1200))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_text_guess.html")

def register(app):
    app.register_blueprint(bp)