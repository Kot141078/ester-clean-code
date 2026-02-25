# -*- coding: utf-8 -*-
"""routes/whatsapp_webhook.py - verifikatsiya i priem vkhodyaschikh iz WhatsApp Cloud API.

MOSTY:
- (Yavnyy) GET /webhooks/whatsapp - Verify Token dance; POST - sobytiya, teksty → roles.store.upsert_observation().
- (Skrytyy #1) agent_id beretsya po klyuchu contact_key=whatsapp:<wa_id>.
- (Skrytyy #2) Oshibki/nestandartnye sobytiya - 200 OK (idempotentnost), bez pobochnykh effektov.

ZEMNOY ABZATs:
Legalnaya integratsiya WhatsApp s obucheniem na realnykh dialogakh - bez “khakov” i obkhoda pravil.

# c=a+b"""
from __future__ import annotations

import os
from typing import Any, Dict
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from roles.store import get_agent_by_key, upsert_observation
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_VERIFY = os.getenv("WHATSAPP_VERIFY_TOKEN","")

router = APIRouter()

@router.get("/webhooks/whatsapp", response_class=PlainTextResponse)
async def whatsapp_verify(mode: str = "", challenge: str = "", verify_token: str = "", hub_mode: str = "", hub_challenge: str = "", hub_verify_token: str = ""):
    # podderzhim i ?hub.* i bez prefiksov
    token = hub_verify_token or verify_token
    if _VERIFY and token == _VERIFY:
        return PlainTextResponse(hub_challenge or challenge or "", status_code=200)
    return PlainTextResponse("forbidden", status_code=403)

@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(req: Request):
    try:
        payload = await req.json()
    except Exception:
        return JSONResponse({"ok": True})  # ne validnyy JSON - ignorim
    try:
        entries = payload.get("entry", [])
        for e in entries:
            for ch in e.get("changes", []):
                val = ch.get("value", {})
                msgs = val.get("messages", [])
                for m in msgs:
                    wa_from = str(m.get("from") or "")
                    txt = ""
                    if m.get("type") == "text":
                        txt = str((m.get("text") or {}).get("body") or "")
                    elif "button" in m:
                        txt = str((m.get("button") or {}).get("text") or "")
                    if wa_from and txt:
                        agent_id = get_agent_by_key(f"whatsapp:{wa_from}")
                        if agent_id:
                            upsert_observation(agent_id, txt, "whatsapp", {"wa_from": wa_from, "id": str(m.get("id") or "")})
    except Exception:
        pass
    return JSONResponse({"ok": True})

def mount_whatsapp_webhook(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app