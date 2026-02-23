# -*- coding: utf-8 -*-
"""
routes/audio_drama_routes.py - REST: /audio/drama/* (prepare/render)

Mosty:
- Yavnyy: (Veb ↔ TTS/FFmpeg) svoboda vybora golosa i sborka dorozhek.
- Skrytyy #1: (Passport ↔ Trassirovka) logiruem razmetku i render.
- Skrytyy #2: (Media/RAG ↔ Navigatsiya) teksty mozhno dobavlyat v pamyat.

Zemnoy abzats:
Na vkhod - skript s rolyami, na vykhod - WAV i SRT. Dalshe mozhno montirovat kak ugodno.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("audio_drama_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.audio.drama import prepare as _prep, render as _rend  # type: ignore
except Exception:
    _prep=_rend=None  # type: ignore

@bp.route("/audio/drama/prepare", methods=["POST"])
def api_prepare():
    if _prep is None: return jsonify({"ok": False, "error":"drama_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_prep(str(d.get("script","")), dict(d.get("cast") or {})))

@bp.route("/audio/drama/render", methods=["POST"])
def api_render():
    if _rend is None: return jsonify({"ok": False, "error":"drama_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_rend(list(d.get("lines") or []), str(d.get("out_dir","data/creator/drama"))))
# c=a+b