
# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.reports.http - minimalnyy HTTP‑router otchetov (bez avtopodklyucheniya).
Mosty:
- Yavnyy: get_fastapi_router(prefix), register_fastapi(app, prefix), register_flask(app, prefix).
- Skrytyy #1: (DX ↔ Sovmestimost) — bez avtozagruzki, ty sam reshaesh podklyuchat or net.
- Skrytyy #2: (Kachestvo ↔ Prozrachnost) — otdaem markdown‑svodku i ping.

Zemnoy abzats:
Deshevyy web‑“stetoskop”: bystryy endpoynt, kotoryy pokazyvaet svodku sostoyaniya — bez tyazhelykh zavisimostey.
# c=a+b"""
import os
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
_PREFIX = os.getenv("ESTER_REPORTS_PREFIX", "/compat/reports")

def _build_md():
    from modules.reports.summary import build_summary, render_markdown
    src = {"entities": [{"id":"ester"}], "edges":[{"rel":"uses"}]}
    sm = build_summary(src)
    return render_markdown(sm, "Ester — Summary")

# ---- FastAPI ----
def get_fastapi_router(prefix: Optional[str]=None):
    try:
        from fastapi import APIRouter, Response
    except Exception as e:
        raise RuntimeError("FastAPI not available") from e
    router = __import__("fastapi").APIRouter(prefix=(prefix or _PREFIX))  # type: ignore
    @router.get("/ping")
    def _ping():
        return {"ok": True, "mod": "reports.http"}
    @router.get("/summary", response_class=__import__("fastapi").Response)  # type: ignore
    def _summary():
        return Response(content=_build_md(), media_type="text/markdown")
    return router

def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        router = get_fastapi_router(prefix)
    except Exception:
        return False
    try:
        app.include_router(router)
        return True
    except Exception:
        return False

# ---- Flask ----
def register_flask(app, prefix: Optional[str]=None) -> bool:
    prefix = prefix or _PREFIX
    try:
        from flask import Response
    except Exception as e:
        raise RuntimeError("Flask not available") from e
    @app.get(prefix + "/ping")
    def _ping():
        return {"ok": True, "mod": "reports.http"}
    @app.get(prefix + "/summary")
    def _summary():
        return Response(_build_md(), mimetype="text/markdown")
    return True