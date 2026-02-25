# -*- coding: utf-8 -*-
"""routes.email_routes - bazovyy mount dlya email-podsistemy cherez FastAPI.

MOSTY:
- Yavnyy: (Flask ↔ FastAPI) montiruem ASGI-prilozhenie pod /email.
- Skrytyy #1: (Diagnostika ↔ UI) /email/ping - bystryy sanity-chek.
- Skrytyy #2: (Evolyutsiya ↔ Kontrakty) ostavlyaet prostranstvo dlya rashshireniya bez lomki API.

ZEMNOY ABZATs:
Do so, chtoby import modulya email-marshrutov ne padal i byl ping-endpoint.

# c=a+b"""
from __future__ import annotations
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def mount_email_routes(app):
    try:
        from fastapi import FastAPI
    except Exception:
        # if there is no FastAPI, it exits quietly (there will already be a warning in the logs)
        return False

    fa = FastAPI(title="Ester Email")
    @fa.get("/ping")
    def ping():
        return {"ok": True, "svc": "email"}

    # Flask-patch include_router daet nam mount ASGI pod prefiks
    return app.include_router(fa, prefix="/email")


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
# stub for email_rutes: no power supply/router/register_*_rutes yet
def register(app):
    return True

# === /AUTOSHIM ===