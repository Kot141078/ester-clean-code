# -*- coding: utf-8 -*-
"""routes/webhook_probe.py - offflayn-proverka konfiguratsii Telegram/WhatsApp webhook.

MOSTY:
- (Yavnyy) GET /admin/webhooks/probe - vozvraschaet gotovye URL, khesh-sekrety i chto esche zapolnit.
- (Skrytyy #1) Ne delaet setevykh zaprosov; vse po ENV, mozhno ispolzovat v closed_box.
- (Skrytyy #2) Otdaet “can-curl” podskazki dlya bystroy registratsii khuka.

ZEMNOY ABZATs:
How “sukhoy progon” provodki: vidim, kuda pridet zapros, kakoy sekret zhdem, i chto vklyuchit v.env.

# c=a+b"""
from __future__ import annotations
import os, hmac, hashlib
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("webhook_probe", __name__, url_prefix="/admin/webhooks")

def register(app):
    app.register_blueprint(bp)

def _h(key: str, msg: str) -> str:
    return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

@bp.get("/probe")
def probe():
    base = os.getenv("TELEGRAM_BASE_URL", "http://127.0.0.1:8000")
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN","")
    tg_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET","")
    wa_token = os.getenv("WHATSAPP_ACCESS_TOKEN","")
    wa_pnid = os.getenv("WHATSAPP_PHONE_NUMBER_ID","")
    verify = os.getenv("WHATSAPP_VERIFY_TOKEN","")
    # We construct a URL (drop-in: do not change existing handles)
    tg_url = f"{base.rstrip('/')}/telegram/webhook"
    wa_url = f"{os.getenv('WHATSAPP_GRAPH_BASE','https://graph.facebook.com/v20.0').rstrip('/')}/{wa_pnid}/messages"
    can_curl_tg = f"curl -s -X POST 'https://api.telegram.org/bot{tg_token}/setWebhook' -d 'url={tg_url}?secret={tg_secret}'"
    can_curl_wa = f"curl -s -X GET '{wa_url}?hub.mode=subscribe&hub.verify_token={verify}&hub.challenge=ping'"

    sample_sig = _h(os.getenv("P2P_HMAC_KEY","devkey"), "POST|/api/v2/synergy/assign|<ts>|<sha256(body)>")
    return jsonify({
        "ok": True,
        "telegram": {
            "webhook_url": tg_url,
            "token_set": bool(tg_token),
            "secret_set": bool(tg_secret),
            "set_webhook_curl": can_curl_tg,
        },
        "whatsapp": {
            "phone_number_id_set": bool(wa_pnid),
            "access_token_set": bool(wa_token),
            "verify_token_set": bool(verify),
            "subscribe_example": can_curl_wa,
        },
        "p2p_assign_sample_sig": sample_sig
    })
# c=a+b