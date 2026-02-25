# -*- coding: utf-8 -*-
"""routes/whatsapp_control_routes.py - Sluzhebnye kontroly WA i predprosmotr stilya.

Mosty:
- (Yavnyy) Predprosmotr stilya - prozrachnoe decision “what exactly is pisat”.
- (Skrytyy #1) Enderton - predikaty na osnove audience/intent.
- (Skrytyy #2) Shennon - minimalnyy vvod → vosproizvodimyy vyvod (templeyty + evristiki).

Zemnoy abzats:
Daet bezopasnyy UI/API dlya predvaritelnoy proverki togona, prezhde chem vklyuchat rassylki.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, request, jsonify
from modules.persona_style import choose_style, render_message
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("whatsapp_control_routes", __name__)

@bp.route("/wa/ctrl/api/style/preview", methods=["POST"])
def wa_style_preview():
    """
    body: { audience, intent, content }
    -> { audience, intent, style: {...}, render: "..." }
    """
    j = request.get_json(force=True, silent=True) or {}
    audience = (j.get("audience") or "neutral").strip().lower()
    intent = (j.get("intent") or "update").strip().lower()
    content = (j.get("content") or "").strip()

    style = choose_style(audience=audience, intent=intent)
    render = render_message(audience=audience, intent=intent, content=content)

    return jsonify({
        "audience": audience,
        "intent": intent,
        "style": style,
        "render": render
    }), 200


def register(app):
    app.register_blueprint(bp)
    return bp