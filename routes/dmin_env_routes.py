# -*- coding: utf-8 -*-
"""
routes/admin_env_routes.py - bezopasnyy runtime-kontrol ENV (whitelist).

MOSTY:
- (Yavnyy) /admin/runtime/env GET/POST - edinaya tochka vklyucheniya "chelovechnogo" tona, sovetnika i dr.
- (Skrytyy #1) Menyaet tolko whitelisted klyuchi; chast - "zhivye" (vliyayut srazu), chast - potrebuyut restart.
- (Skrytyy #2) Nichego ne lomaet: eto nadstroyka nad os.environ; suschestvuyuschie moduli chitayut ENV kak i ranshe.

ZEMNOY ABZATs:
Vklyuchit «chelovechnyy» stil rassylok ili pomenyat rezhim sovetnika bez deploya - pryamo iz brauzera.

# c=a+b
"""
from __future__ import annotations

import os, time
from typing import Any, Dict, List
from fastapi import APIRouter, FastAPI, Body
from fastapi.responses import JSONResponse
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

# kakie klyuchi pozvoleno menyat cherez UI
WHITELIST = {
    # live - chitayutsya pri kazhdom vyzove → vliyayut srazu
    "NUDGES_USE_STYLED": {"live": True,  "desc": "Chelovechnyy stil soobscheniy (0/1)"},
    "ADVISOR_MODE":      {"live": True,  "desc": "Rezhim sovetnika A(lokalno)/B(delegat)"},
    "ADVISOR_BLEND":     {"live": True,  "desc": "Ves podskazki v overlay (0..1)"},
    "ROLE_CLARIFY_THRESHOLD": {"live": True, "desc":"Porog neuverennosti profilya (0..1)"},
    # static - chitayutsya pri importe modulya → mozhet potrebovatsya restart
    "TELEGRAM_TYPING_DELAY_MS": {"live": False, "desc": "Imitatsiya nabora (ms)"},
    "TELEGRAM_ALLOWED_CHATS":   {"live": False, "desc": "Belyy spisok chat_id (csv)"},
    "ROLE_EDGE_DECAY":          {"live": False, "desc": "Zatukhanie affinnosti/den (0..1)"},
}

def _current_state() -> Dict[str, Any]:
    out = {"ts": int(time.time()), "entries": []}
    for k, meta in WHITELIST.items():
        out["entries"].append({
            "key": k, "value": os.getenv(k, ""), "live": bool(meta["live"]),
            "desc": meta["desc"]
        })
    return out

@router.get("/admin/runtime/env")
async def admin_env_get():
    return JSONResponse({"ok": True, **_current_state()})

@router.post("/admin/runtime/env")
async def admin_env_post(payload: Dict[str, Any] = Body(...)):
    changed = []
    for k, v in (payload or {}).items():
        if k in WHITELIST:
            os.environ[k] = "" if v is None else str(v)
            changed.append({"key": k, "value": os.environ[k], "live": WHITELIST[k]["live"]})
    return JSONResponse({"ok": True, "changed": changed, **_current_state()})

def mount_admin_env(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app