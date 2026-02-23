# -*- coding: utf-8 -*-
"""
routes/whatsapp_send_routes.py - Otpravka soobscheniy v WhatsApp Cloud API.

Mosty:
- (Yavnyy) Otpravka cherez Meta Graph API v16+ (unifitsirovannyy POST messages).
- (Skrytyy #1) Cover & Thomas - «minimalnyy signal» razlichaet dry/real: side-effect kapsulirovan.
- (Skrytyy #2) Regulyatsiya A/B (env MSG_STYLE_AB) - bystryy otkat stilya bez regressiy.

Zemnoy abzats:
Daet API `/wa/send` dlya universalnoy otpravki i lokalnogo dry-run bez interneta.
Variant A (po umolchaniyu) - «bezopasnaya» otpravka: esli token pustoy → tolko dry-run.

# c=a+b
"""
from __future__ import annotations
import os
import json
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify, current_app
from modules.messenger_bridge import WhatsAppSender
from modules.persona_style import render_message
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("whatsapp_send_routes", __name__)

WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_TIMEOUT = float(os.environ.get("WHATSAPP_TIMEOUT", "6.0"))

@bp.route("/wa/send", methods=["POST"])
def wa_send():
    """
    Unifitsirovannaya otpravka:
    body: { to: str, text?: str, audience?: str, intent?: str, content?: str, meta?: {} }
    query: dry_run=1 - prinuditelno ne khodit v vneshniy API.
    """
    j = request.get_json(force=True, silent=True) or {}
    to = (j.get("to") or "").strip()
    text = j.get("text")
    audience = j.get("audience")  # lawyer|student|friend|business|neutral|...
    intent = j.get("intent")      # letter|reminder|update|apology|request|...
    content = j.get("content")    # syroy smysl/fakty, esli text ne zadan

    if not to or (not text and not content):
        return jsonify({"ok": False, "error": "to_or_text_missing"}), 400

    # Esli zadana «semantika», to formiruem tekst cherez dvizhok stilya.
    if not text:
        text = render_message(audience=audience or "neutral",
                              intent=intent or "update",
                              content=content or "")

    dry_param = request.args.get("dry_run")
    dry_run = (dry_param == "1") or not (WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID)

    sender = WhatsAppSender(
        access_token=WHATSAPP_ACCESS_TOKEN,
        phone_number_id=WHATSAPP_PHONE_NUMBER_ID,
        timeout=WHATSAPP_TIMEOUT,
    )

    ok, result = sender.send_text(to=to, text=text, dry_run=dry_run)
    status = 200 if ok else 502
    return jsonify({
        "ok": ok,
        "dry_run": dry_run,
        "to": to,
        "text": text,
        "result": result
    }), status


def register(app):
    app.register_blueprint(bp)
    return bp