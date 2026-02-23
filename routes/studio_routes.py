# -*- coding: utf-8 -*-
"""
routes/studio_routes.py - REST: studiya kontenta (prompty, audio, video, muzyka, Patreon).

Mosty:
- Yavnyy: (Veb ↔ Studiya) edinaya tochka starta dlya tvorcheskikh konveyerov.
- Skrytyy #1: (FFmpeg/TTS ↔ Bezopasnost) operatsii pomecheny v politike predostorozhnosti.
- Skrytyy #2: (Garazh/Flot ↔ Integratsiya) rezultat mozhno dobavlyat v proekty/portfolio.

Zemnoy abzats:
Knopki «sdelat ideyu», «ozvuchit», «skleit video», «podgotovit Patreon» - vse pod rukoy.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os, glob, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("studio_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.studio.prompts import trending as _trending  # type: ignore
    from modules.studio.tts import drama as _drama  # type: ignore
    from modules.studio.video import render as _render  # type: ignore
    from modules.studio.music import generate as _music  # type: ignore
    from modules.monetize.patreon import kit as _kit  # type: ignore
except Exception:
    _trending=_drama=_render=_music=_kit=None  # type: ignore

@bp.route("/studio/prompt/trending", methods=["POST"])
def api_trending():
    if _trending is None: return jsonify({"ok": False, "error":"studio_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_trending(list(d.get("topics") or []), str(d.get("persona","ekspert"))))

@bp.route("/studio/audio/drama", methods=["POST"])
def api_drama():
    if _drama is None: return jsonify({"ok": False, "error":"studio_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_drama(str(d.get("title","Audio")), list(d.get("roles") or []), list(d.get("script") or [])))

@bp.route("/studio/video/render", methods=["POST"])
def api_render():
    if _render is None: return jsonify({"ok": False, "error":"studio_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_render(str(d.get("title","Video")), str(d.get("mode","short")), str(d.get("aspect","9:16")), d.get("duration"), list(d.get("text_subs") or []), d.get("bgm"), int(d.get("fps",30))))

@bp.route("/studio/music/generate", methods=["POST"])
def api_music():
    if _music is None: return jsonify({"ok": False, "error":"studio_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_music(int(d.get("seconds",10)), int(d.get("bpm",100)), str(d.get("scale","Amin"))))

@bp.route("/studio/patreon/kit", methods=["POST"])
def api_patreon():
    if _kit is None: return jsonify({"ok": False, "error":"studio_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_kit(str(d.get("creator","Ester System")), list(d.get("tiers") or []), str(d.get("welcome","Spasibo!")), list(d.get("posts") or [])))

@bp.route("/studio/exports", methods=["GET"])
def api_exports():
    root=os.getenv("STUDIO_OUT","data/studio/out")
    files=sorted(glob.glob(os.path.join(root,"*.*")))
    return jsonify({"ok": True, "files": files})
# c=a+b