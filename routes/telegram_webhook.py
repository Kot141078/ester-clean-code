# -*- coding: utf-8 -*-
"""routes/telegram_webhook.py - priem apdeytov Telegram i prokladka v RoleDiscovery.

MOSTY:
- (Yavnyy) /webhooks/telegram - prinimaet apdeyty, proveryaet sekret-v zagolovke, prokidyvaet v roles.store.upsert_observation().
- (Skrytyy #1) agent_id opredelyaetsya cherez obratnyy indeks contact_key=telegram:<chat_id>.
- (Skrytyy #2) Myagkaya degradatsiya: esli agent ne smeplen - prosto 200 OK bez pobochek.

ZEMNOY ABZATs:
Lyuboe chelovecheskoe soobschenie uchit Ester - bez lishnikh voprosov i form.

# c=a+b"""
from __future__ import annotations

import os
from typing import Any, Dict
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from roles.store import get_agent_by_key, upsert_observation
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET","")

router = APIRouter()

@router.post("/webhooks/telegram")
async def telegram_webhook(req: Request):
    if _SECRET:
        sec = req.headers.get("X-Telegram-Bot-Api-Secret-Token","")
        if sec != _SECRET:
            return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    payload = await req.json()
    msg = payload.get("message") or payload.get("edited_message") or {}
    chat = (msg.get("chat") or {})
    chat_id = str(chat.get("id") or "")
    text = str(msg.get("text") or "")
    if chat_id and text:
        agent_id = get_agent_by_key(f"telegram:{chat_id}")
        if agent_id:
            upsert_observation(agent_id, text, "telegram", {"from_id": str((msg.get('from') or {}).get('id') or ""), "msg_id": str(msg.get("message_id") or "")})
    return JSONResponse({"ok": True})

def mount_telegram_webhook(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app