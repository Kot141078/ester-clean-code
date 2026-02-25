# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.compat.chat_rag_http - kompaktnyy HTTP‑khuk dlya RAG‑otveta.
Register (FastAPI/Flask):
- GET `/compat/chat/rag/ping`
- POST `/compat/chat/rag_answer` { "q": "..." } -> {ok,text,mode,meta}

Mosty:
- Yavnyy: vyzyvaet modules.thinking.compat_actions.rag_answer
- Skrytyy #1: uvazhaet A/B (ESTER_THINK_RAG_AB)
- Skrytyy #2: put sovmestim s suschestvuyuschey arkhitekturoy /compat/*

Zemnoy abzats:
Eto “knopka otvetit po lokalnym znaniyam”: mozhno bez zapuska osnovnogo chata proverit svyazku ingest→RAG→otvet.
# c=a+b"""
import os, json
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PREFIX = os.getenv("ESTER_CHAT_PREFIX", "/compat/chat")

def _json(o):  # a small helper without unnecessary dependencies
    import json as _j
    return _j.dumps(o, ensure_ascii=False)

def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response, Body
        from modules.thinking import compat_actions as ca
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/rag/ping", response_class=__import__("fastapi").Response)  # type: ignore
    def _ping():
        return Response(content=_json({"ok": True, "where": "rag"}), media_type="application/json")
    @app.post(prefix + "/rag_answer", response_class=__import__("fastapi").Response)  # type: ignore
    def _answer(payload: dict = Body(...)):
        q = str((payload or {}).get("q",""))
        res = ca.rag_answer(q)
        return Response(content=_json(res), media_type="application/json")
    return True

def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import Response, request
        from modules.thinking import compat_actions as ca
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/rag/ping")
    def _ping():
        return Response(_json({"ok": True, "where": "rag"}), mimetype="application/json")
    @app.post(prefix + "/rag_answer")
    def _answer():
        data = request.get_json(silent=True) or {}
        q = str(data.get("q",""))
        res = ca.rag_answer(q)
        return Response(_json(res), mimetype="application/json")
    return True