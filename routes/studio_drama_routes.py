# -*- coding: utf-8 -*-
"""
routes/studio_drama_routes.py - REST: TTS odnoy frazy i sborka audiodramy.

Mosty:
- Yavnyy: (Veb ↔ Studiya) prostye ruchki dlya sinteza i mnogorolevoy sborki.
- Skrytyy #1: (Profile ↔ Memory) bazovye operatsii uzhe logiruyutsya modulyami.
- Skrytyy #2: (Sotsdeploy ↔ Integratsiya) vykhod mozhno otdat v SocialDeploy dlya publikatsii.

Zemnoy abzats:
Knopki «ozvuchit» i «sobrat dramu» - chtoby tvorit bez lishnikh shagov.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("studio_drama_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.studio.tts import _speech  # type: ignore
    from modules.studio.drama import make as _drama_make, list_all as _drama_list  # type: ignore
except Exception:
    _speech=None; _drama_make=None; _drama_list=None  # type: ignore

@bp.route("/studio/tts/say", methods=["POST"])
def api_tts_say():
    if _speech is None: return jsonify({"ok": False, "error":"tts_unavailable"}), 500
    d=request.get_json(True, True) or {}
    text=str(d.get("text",""))[:5000]
    voice=str(d.get("voice","")) or None
    import os, time
    root=os.getenv("TTS_ROOT","data/studio/tts"); os.makedirs(root, exist_ok=True)
    path=os.path.join(root, f"say_{int(time.time())}.wav")
    ok=_speech(text, voice, path)
    rep={"ok": ok, "wav": path}
    return jsonify(rep)

@bp.route("/studio/drama/make", methods=["POST"])
def api_drama_make():
    if _drama_make is None: return jsonify({"ok": False, "error":"drama_unavailable"}), 500
    d=request.get_json(True, True) or {}
    title=str(d.get("title","Untitled"))
    script=list(d.get("script") or [])
    voices=dict(d.get("voices") or {})
    gap=int(d.get("gap_ms", 250))
    return jsonify(_drama_make(title, script, voices, gap))

@bp.route("/studio/drama/list", methods=["GET"])
def api_drama_list():
    if _drama_list is None: return jsonify({"ok": False, "error":"drama_unavailable"}), 500
    return jsonify(_drama_list())
# c=a+b