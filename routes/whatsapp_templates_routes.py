# -*- coding: utf-8 -*-
"""routes/whatsapp_templates_routes.py - REST-obertka otpravki HSM-shablonov WhatsApp po spisku contact_key.

MOSTY:
- (Yavnyy) POST /whatsapp/send_template → keys[], template, lang?, body_params[], header_params[], buttons[].
- (Skrytyy #1) Marshrutiziruem tolko keys s prefiksom 'whatsapp:' (ostalnye tikho propuskaem).
- (Skrytyy #2) Metriki (sent/skipped/by_key) prigodny dlya alertov/bordy i treysinga “pochemu ne ushlo”.

ZEMNOY ABZATs:
Odin vyzov - i vashi soglasovannye shablony ukhodyat lyudyam, dazhe esli okno 24 hours zakryto.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, FastAPI, Body
from fastapi.responses import JSONResponse

from messaging.adapters.whatsapp_hsm import send_template as _send_hsm
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

@router.post("/whatsapp/send_template")
async def whatsapp_send_template(payload: Dict[str, Any] = Body(...)):
    keys = [str(k) for k in (payload.get("keys") or [])]
    template = str(payload.get("template") or "")
    lang = payload.get("lang")
    body_params = payload.get("body_params") or []
    header_params = payload.get("header_params") or []
    buttons = payload.get("buttons") or []

    if not keys or not template:
        return JSONResponse({"ok": False, "error": "keys[] and template required"}, status_code=400)

    sent = skipped = 0
    by_key: Dict[str, Dict[str,int]] = {}
    for k in keys:
        if not k.startswith("whatsapp:"):
            skipped += 1
            by_key[k] = {"sent":0,"skipped":1}
            continue
        res = _send_hsm(k, template, lang=lang, body_params=body_params, header_params=header_params, buttons=buttons)
        s = int(res.get("sent",0)); f = int(res.get("skipped",0))
        sent += s; skipped += f
        by_key[k] = {"sent": s, "skipped": f}
    return JSONResponse({"ok": True, "sent": sent, "skipped": skipped, "by_key": by_key})

def mount_whatsapp_templates(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app