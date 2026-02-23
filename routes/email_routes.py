# -*- coding: utf-8 -*-
"""
routes.email_routes - bazovyy mount dlya email-podsistemy cherez FastAPI.

MOSTY:
- Yavnyy: (Flask ↔ FastAPI) montiruem ASGI-prilozhenie pod /email.
- Skrytyy #1: (Diagnostika ↔ UI) /email/ping - bystryy sanity-chek.
- Skrytyy #2: (Evolyutsiya ↔ Kontrakty) ostavlyaet prostranstvo dlya rasshireniya bez lomki API.

ZEMNOY ABZATs:
Delaet tak, chtoby import modulya email-marshrutov ne padal i byl ping-endpoint.

# c=a+b
"""
from __future__ import annotations
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def mount_email_routes(app):
    try:
        from fastapi import FastAPI
    except Exception:
        # esli FastAPI net - tikho vykhodim (v logakh uzhe budet preduprezhdenie)
        return False

    fa = FastAPI(title="Ester Email")
    @fa.get("/ping")
    def ping():
        return {"ok": True, "svc": "email"}

    # Flask-patch include_router daet nam mount ASGI pod prefiks
    return app.include_router(fa, prefix="/email")


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
# zaglushka dlya email_routes: poka net bp/router/register_*_routes
def register(app):
    return True

# === /AUTOSHIM ===