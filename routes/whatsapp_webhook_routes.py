# -*- coding: utf-8 -*-
"""routes/whatsapp_webhook_routes.py - Webhook dlya WhatsApp Cloud API.

Mosty:
- (Yavnyy) HTTP-vebkhuk Meta: verifikatsiya po hub.verify_token (RFC 7231 sovmestimyy otvet).
- (Skrytyy #1) Ashbi - minimalnyy regulyator: odin universalnyy priemnik entry/changes.
- (Skrytyy #2) Dzheynes - pravdopodobie sobytiy: logiruem tolko fact i tip, PII ne sokhranyaem.

Zemnoy abzats:
Fayl daet “tverdoe soedinenie” WA↔Ester: proverka tokena GET i priem POST apdeytov.
Rabotaet v zakrytoy korobke (dry) i v boyu - bez izmeneniya suschestvuyuschikh kontraktov.

# c=a+b"""
from __future__ import annotations
import os
import json
import time
from typing import Any, Dict

from flask import Blueprint, request, jsonify, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("whatsapp_webhook_routes", __name__)

# Bezopasnye defolty
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "devcheck")
# For combat sending, see rutes/whatsapp_send_rutes.po

@bp.route("/api/whatsapp/webhook", methods=["GET"])
def wa_webhook_verify():
    """Webhook verification using the Meta protocol (GET ?nub.*).
    Returns hub.challenge when verification_token matches."""
    mode = request.args.get("hub.mode", "")
    token = request.args.get("hub.verify_token", "")
    challenge = request.args.get("hub.challenge", "")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return challenge, 200
    return "forbidden", 403


@bp.route("/api/whatsapp/webhook", methods=["POST"])
def wa_webhook_inbound():
    """Priem vkhodyaschikh apdeytov.
    Podderzhivaet uproschennyy format entry/changes from WA Cloud API.
    Nothing ne lomaem: sobytie adaptiruem v unifitsirovannyy “vkhod” Ester."""
    try:
        payload: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        # Minimal normalization: take the text of the last message, if any.
        msg_text = None
        from_id = None
        try:
            changes = payload.get("entry", [])[0].get("changes", [])
            value = changes[0].get("value", {}) if changes else {}
            msgs = value.get("messages", []) or []
            if msgs:
                last = msgs[-1]
                from_id = last.get("from")
                if last.get("type") == "text":
                    msg_text = (last.get("text") or {}).get("body")
        except Exception:
            pass

        # Log event - only fact and type (no FDI):
        current_app.logger.info("[WA] inbound: text=%s, anon_from=%s, t=%s",
                                bool(msg_text), bool(from_id), int(time.time()))

        # This is where internal thought/memory pipelines can be invoked if needed.
        # We don’t do this by default: drop-in and no-regression.

        return jsonify({"ok": True}), 200
    except Exception as e:
        current_app.logger.warning("[WA] inbound error: %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "bad_request"}), 400


def register(app):
    """Registration function (select rutes/register_all.by)."""
    app.register_blueprint(bp)
    return bp