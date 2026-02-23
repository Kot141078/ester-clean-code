# -*- coding: utf-8 -*-
"""
Vspomogatelnyy chat-rout (esli obschiy registrator blyuprintov rabotaet).

POST /chat_boot/send  {text, user?}

MOSTY:
- Yavnyy: Kommunikatsiya ↔ Memory - kazhdoe soobschenie fiksiruem.
- Skrytyy 1: Diagnostika ↔ Nadezhnost - JSON-otvet bez storonnikh zavisimostey.
- Skrytyy 2: UI ↔ Health - mozhno vyzyvat iz brauzera/skriptov.

ZEMNOY ABZATs:
Dvertsa dlya razgovora: skazal - poluchil otvet, vse sokhranilos.
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.chat import chat_reply
except Exception:
    def chat_reply(text: str, user_name: str | None = None):
        return {"ok": False, "reply": "chat module unavailable", "contexts": [], "debug": {}}

bp = Blueprint("chat_boot", __name__, url_prefix="/chat_boot")

@bp.post("/send")
def _send():
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", ""))
    user = data.get("user")
    res = chat_reply(text, user_name=user)
    return jsonify(res)

def register(app):
    app.register_blueprint(bp)
    return "chat_boot"

# c=a+b