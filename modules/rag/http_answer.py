# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.rag.http_answer - HTTP ruchka dlya RAG answers.
Register POST `/compat/rag/answer` (FastAPI/Flask).
# c=a+b"""
import os, json
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PREFIX = os.getenv("ESTER_RAG_PREFIX","/compat/rag")

def _json(o) -> str:
    return json.dumps(o, ensure_ascii=False, indent=2)

def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response, Body
    except Exception:
        return False
    prefix = prefix or _PREFIX
    from modules.rag import answer as ra
    @app.post(prefix + "/answer", response_class=__import__("fastapi").Response)  # type: ignore
    def _answer(payload: dict = Body(...)):
        q = payload.get("q","")
        k = int(payload.get("k", 5))
        return Response(content=_json(ra.answer(q, k)), media_type="application/json")
    return True

def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import request, Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    from modules.rag import answer as ra
    @app.post(prefix + "/answer")
    def _answer():
        payload = (request.get_json(force=True, silent=True) or {})
        q = payload.get("q","")
        k = int(payload.get("k", 5))
        return Response(_json(ra.answer(q, k)), mimetype="application/json")
    return True