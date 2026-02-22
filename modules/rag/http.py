
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.rag.http — HTTP‑ruchki RAG (bez avtopodklyucheniya).
Mosty:
- Yavnyy: /compat/rag/{status,search,upsert} dlya FastAPI/Flask.
- Skrytyy #1: (DX ↔ Sovmestimost) — JSON‑kontrakty bez vneshnikh paketov.
- Skrytyy #2: (Memory ↔ Poisk) — pryamoy most k modules.rag.hub.

Zemnoy abzats:
Legkiy «port» v RAG: polozhit tekst, nayti pokhozhee, posmotret status — bez tyazhelykh servisov.
# c=a+b
"""
import os, json
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
_PREFIX = os.getenv("ESTER_RAG_PREFIX","/compat/rag")

def _json(o) -> str:
    return json.dumps(o, ensure_ascii=False, indent=2)

# FastAPI
def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response, Body
    except Exception:
        return False
    prefix = prefix or _PREFIX
    from modules.rag import hub
    @app.get(prefix + "/status", response_class=__import__("fastapi").Response)  # type: ignore
    def _status():
        return Response(content=_json(hub.status()), media_type="application/json")
    @app.post(prefix + "/upsert", response_class=__import__("fastapi").Response)  # type: ignore
    def _upsert(payload: dict = Body(...)):
        text = payload.get("text","")
        meta = payload.get("meta",{})
        idv = payload.get("id")
        return Response(content=_json(hub.upsert(text=text, meta=meta, id=idv)), media_type="application/json")
    @app.post(prefix + "/search", response_class=__import__("fastapi").Response)  # type: ignore
    def _search(payload: dict = Body(...)):
        q = payload.get("q","")
        k = int(payload.get("k", 5))
        return Response(content=_json(hub.search(q, k)), media_type="application/json")
    return True

# Flask
def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import request, Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    from modules.rag import hub
    @app.get(prefix + "/status")
    def _status():
        return Response(_json(hub.status()), mimetype="application/json")
    @app.post(prefix + "/upsert")
    def _upsert():
        payload = request.get_json(force=True, silent=True) or {}
        return Response(_json(hub.upsert(text=payload.get("text",""), meta=payload.get("meta",{}), id=payload.get("id"))), mimetype="application/json")
    @app.post(prefix + "/search")
    def _search():
        payload = request.get_json(force=True, silent=True) or {}
        return Response(_json(hub.search(payload.get("q",""), int(payload.get("k",5)))), mimetype="application/json")
    return True