# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict

import httpx
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_API_BASE = os.getenv("ESTER_API_BASE", "http://127.0.0.1:8010").rstrip("/")


def _infer_intent(text: str) -> str:
    t = (text or "").strip().lower()
    if any(k in t for k in ("pochemu", "kak", "zachem", "chto takoe", "chto eto", "?")):
        return "RESEARCH"
    if any(k in t for k in ("reliz", "vyshel", "versiya", "novoe", "izmeneniya", "changelog")):
        return "RELEASES"
    return "CHITCHAT"


async def _post_json(
    client: httpx.AsyncClient, path: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    r = await client.post(f"{_API_BASE}{path}", json=payload, timeout=30.0)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {"answer": r.text or ""}


async def handle_query_async(text: str, name: str) -> Dict[str, Any]:
    payload = {"user": name, "text": text}
    endpoints = ("/chat/ask", "/chat", "/chat/query", "/chat/answer")

    async with httpx.AsyncClient(trust_env=False) as client:
        last_err = None
        for ep in endpoints:
            try:
                data = await _post_json(client, ep, payload)
                answer = data.get("answer") or data.get("text") or data.get("message") or ""
                intent = data.get("intent") or _infer_intent(text)
                if not answer:
                    ans2 = data.get("result") or {}
                    answer = ans2.get("answer") or ans2.get("text") or ""
                if answer:
                    return {"answer": answer, "intent": intent}
            except Exception as e:
                last_err = e
                continue

    msg = "Izvini, ne poluchilos sobrat otvet. Server seychas zanyat — poprobuy esche raz."
    if last_err:
        msg += f" (diag: {type(last_err).__name__})"
# return {"answer": msg, "intent": _infer_intent(text)}