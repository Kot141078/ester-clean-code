# -*- coding: utf-8 -*-
"""routes/audio_stt_routes.py - REST: /audio/stt/transcribe, /audio/stt/get

Mosty:
- Yavnyy: (Veb ↔ STT) tochka vkhoda dlya ruchnogo i programmnogo vyzova.
- Skrytyy #1: (Profile ↔ Trassirovka) pishet stt_done v zhurnal.
- Skrytyy #2: (RAG ↔ Navigatsiya) teksty dostupny po id dlya posleduyuschego poiska.

Zemnoy abzats:
Odin POST - i u vas transkriptsiya s subtitrami, prigodnaya dlya indeksatsii i montazha.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, send_file
import os, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("audio_stt_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.audio.stt import transcribe as _stt  # type: ignore
except Exception:
    _stt=None  # type: ignore

@bp.route("/audio/stt/transcribe", methods=["POST"])
def api_transcribe():
    if _stt is None: return jsonify({"ok": False, "error":"stt_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_stt(str(d.get("path","")), str(d.get("lang") or "") or None, str(d.get("out_dir") or "") or None))

@bp.route("/audio/stt/get", methods=["GET"])
def api_get():
    rid=str(request.args.get("id",""))
    fmt=str(request.args.get("format","txt")).lower()
    base=os.path.join(os.getenv("STT_DIR","data/stt"), rid)
    if not os.path.isdir(base):
        return jsonify({"ok": False, "error":"id_not_found"}), 404
    path={"txt":"transcript.txt","srt":"subtitles.srt","vtt":"subtitles.vtt","json":"meta.json"}.get(fmt,"transcript.txt")
    fp=os.path.join(base, path)
    if not os.path.isfile(fp):
        return jsonify({"ok": False, "error":"file_not_found"}), 404
    mt="text/plain; charset=utf-8" if fmt!="json" else "application/json"
    return send_file(fp, mimetype=mt)
# c=a+b