# -*- coding: utf-8 -*-
"""routes/voice_api_routes.py - API/UI predprosmotra "golosa avtora".

MOSTY:
- (Yavnyy) /voice/api/preview - primenyaet Voice poverkh bazovogo shablona pisma.
- (Skrytyy #1) Sovmestim s tekuschimi intent/audience; ne menyaet suschestvuyuschie API.
- (Skrytyy #2) UI /voice/admin - lokalnyy instrument nastroyki, bez vneshnikh zavisimostey.

ZEMNOY ABZATs:
Pozvolyaet Ester pisat rovno “kak vy privykli”, ne putaya lyudey i ne narushaya pravila ploschadok.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, request, jsonify, render_template
from modules.author_voice import render_with_voice, load_voice
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("voice_api", __name__, url_prefix="/voice", template_folder="../templates")

@bp.route("/api/preview", methods=["POST"])
def voice_preview():
    j = request.get_json(force=True, silent=True) or {}
    audience = (j.get("audience") or "neutral").strip().lower()
    intent = (j.get("intent") or "letter").strip().lower()
    content = (j.get("content") or "").strip()
    voice = j.get("voice") or {}
    text = render_with_voice(audience, intent, content, voice_overrides=voice)
    return jsonify({"ok": True, "audience": audience, "intent": intent, "voice": voice, "text": text})

@bp.route("/admin", methods=["GET"])
def voice_admin():
    v = load_voice()
    return render_template("voice_admin.html", warmth=v.warmth, brevity=v.brevity, formality=v.formality, signature=v.signature, prefix=v.prefix)

def register(app):
    app.register_blueprint(bp)
    return bp