# -*- coding: utf-8 -*-
"""
routes/voice_webrtc_routes.py - REST+UI dlya lokalnogo audio-mosta WebRTC (ruchnoy SDP).

Ruchki:
  POST /voice/offer  {"cid":"room1","sdp":"..."}
  GET  /voice/offer  ?cid=room1
  POST /voice/answer {"cid":"room1","sdp":"..."}
  GET  /voice/answer ?cid=room1
  GET  /admin/voice

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.voice.webrtc_store import store_offer, get_offer, store_answer, get_answer
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("voice_webrtc_routes", __name__, url_prefix="/voice")

@bp.route("/offer", methods=["POST"])
def offer_set():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(store_offer(data.get("cid","room"), data.get("sdp","")))

@bp.route("/offer", methods=["GET"])
def offer_get():
    return jsonify(get_offer(request.args.get("cid","room")))

@bp.route("/answer", methods=["POST"])
def answer_set():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(store_answer(data.get("cid","room"), data.get("sdp","")))

@bp.route("/answer", methods=["GET"])
def answer_get():
    return jsonify(get_answer(request.args.get("cid","room")))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_voice.html")

def register(app):
    app.register_blueprint(bp)