# -*- coding: utf-8 -*-
"""routes/telegram_webhook_routes.py - Telegram Webhook (drop-in bezopasnyy).

MOSTY:
- (Yavnyy) Pryamoy priem apdeytov TG → normalizatsiya → chelovekopodobnaya stilizatsiya otveta.
- (Skrytyy #1) Ne dubliruet route: esli /api/telegram/webhook uzhe zaregistrirovan - akkuratno ne registriruem.
- (Skrytyy #2) Obschaya stilistika cherez modules.persona_style (edinyy ton dlya pisem/chatov).

ZEMNOY ABZATs:
Pozvolyaet “tverdo” podklyuchit TG dazhe esli starye fayly poteryany. Bez tokena - dry-rezhim, nichego naruzhu ne shlet.
# c=a+b"""
from __future__ import annotations
import os
import time
import json
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify, current_app
from modules.persona_style import render_message
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("telegram_webhook_routes", __name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_TIMEOUT = float(os.environ.get("TELEGRAM_TIMEOUT", "6.0"))
TELEGRAM_SECRET_TOKEN = os.environ.get("TELEGRAM_SECRET_TOKEN", "").strip()

def _route_exists(app, rule: str, methods=("POST","GET")) -> bool:
    try:
        for r in app.url_map.iter_rules():
            if r.rule == rule and (not methods or any(m in r.methods for m in methods)):
                return True
    except Exception:
        pass
    return False

@bp.route("/api/telegram/webhook", methods=["GET"])
def tg_webhook_ping():
    # Empty ping for simple checks
    return "ok", 200

@bp.route("/api/telegram/webhook", methods=["POST"])
def tg_webhook():
    # Optional secret header check (if you used the Webhook secret_token set)
    if TELEGRAM_SECRET_TOKEN:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token", "") != TELEGRAM_SECRET_TOKEN:
            return "forbidden", 403

    payload: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    msg = payload.get("message") or payload.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or msg.get("caption") or "").strip()

    # Easy stylization through a common engine (neutral tone).
    if text:
        rendered = render_message(audience="neutral", intent="update", content=text)
    else:
        rendered = "Hello, I'm online."

    # Without a token, we just log and don’t send anything.
    if not TELEGRAM_BOT_TOKEN:
        current_app.logger.info("[TG] dry inbound chat_id=%s text=%s", chat_id, bool(text))
        return jsonify({"ok": True, "dry": True})

    # With a real token, we send an echo response.
    try:
        import urllib.request, urllib.parse, json as _json
        base = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = _json.dumps({"chat_id": chat_id, "text": rendered}).encode("utf-8")
        req = urllib.request.Request(base, data=data, headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=TELEGRAM_TIMEOUT) as resp:
            _ = resp.read()
    except Exception as e:
        current_app.logger.warning("[TG] send error: %s", e, exc_info=True)

    return jsonify({"ok": True})

def register(app):
    # If the project already has such a route, we do not register a duplicate.
    if _route_exists(app, "/api/telegram/webhook", methods=("POST","GET")):
        return None
    app.register_blueprint(bp)
    return bp