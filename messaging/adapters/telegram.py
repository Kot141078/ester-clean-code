# -*- coding: utf-8 -*-
"""
messaging/adapters/telegram.py — otpravka v Telegram Bot API bez vneshnikh zavisimostey.

MOSTY:
- (Yavnyy) send_message(chat_id, text) → dict {ok,http_status,message_id}; uchityvaet imitatsiyu nabora (typing).
- (Skrytyy #1) Logi popytok pishutsya v outbox_store; soglasovano s nudges.retry.
- (Skrytyy #2) Filtr razreshennykh chatov (TELEGRAM_ALLOWED_CHATS) — zaschitnyy barer.

ZEMNOY ABZATs:
Ofitsialnyy i «tikhiy» sposob govorit cherez Telegram ot imeni bota s druzhelyubnym imenem bez slova «bot» v display-name.

# c=a+b
"""
from __future__ import annotations

import json, os, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from typing import Dict, Any

from messaging.outbox_store import record_attempt
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

API_BASE = os.getenv("TELEGRAM_BOT_API_BASE", "https://api.telegram.org").rstrip("/")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TYPING_MS = int(os.getenv("TELEGRAM_TYPING_DELAY_MS","0") or "0")
_ALLOWED = [x.strip() for x in (os.getenv("TELEGRAM_ALLOWED_CHATS","") or "").split(",") if x.strip()]

def _call(method: str, payload: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
    if not TOKEN:
        return (0, {"ok": False, "error": "no token"})
    url = f"{API_BASE}/bot{TOKEN}/{method}"
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type":"application/json"})
    try:
        with urlopen(req, timeout=10) as r:
            code = r.getcode()
            data = json.loads(r.read().decode("utf-8") or "{}")
            return (int(code), data)
    except HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            data = {"description": str(e)}
        return (int(e.code), {"ok": False, **data})
    except URLError as e:
        return (0, {"ok": False, "error": str(e)})

def _allowed(chat_id: str) -> bool:
    return (not _ALLOWED) or (str(chat_id) in _ALLOWED)

def send_message(chat_id: str, text: str) -> Dict[str, Any]:
    channel = "telegram"
    if not _allowed(chat_id):
        record_attempt(channel, chat_id, text, 0, "skip:not-allowed", None, {})
        return {"sent": 0, "skipped": 1}

    # imitatsiya nabora (neobyazatelno)
    if TYPING_MS > 0:
        _call("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        # bez sleep — ne blokiruem tsikl; Telegram pokazhet kratkiy "typing" i tak

    code, data = _call("sendMessage", {"chat_id": chat_id, "text": text, "disable_web_page_preview": True})
    ok = bool(data.get("ok")) and 200 <= code < 300
    msg_id = ""
    if isinstance(data.get("result"), dict):
        msg_id = str(data["result"].get("message_id",""))
    record_attempt(channel, chat_id, text, code, "ok" if ok else "fail", msg_id, data)
    return {"sent": 1 if ok else 0, "skipped": 0 if ok else 1, "http_status": code, "message_id": msg_id, "raw": data}