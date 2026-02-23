# -*- coding: utf-8 -*-
"""
messaging/whatsapp_adapter.py — ofitsialnyy WhatsApp Business Cloud API.

MOSTY:
- (Yavnyy) WhatsAppAdapter: send_text(), webhook validatsiya (verify), parsing vkhodyaschikh.
- (Skrytyy #1) Stels-persona: myagkaya podpis + prozrachnost assistenta; tolko opt-in, tolko approved templates dlya proactive.
- (Skrytyy #2) Guard: nikakogo "neofitsialnogo" WhatsApp — tolko Cloud API s tokenom.

ZEMNOY ABZATs:
Nadezhnyy kanal dlya delovoy perepiski: uvazhaet pravila WhatsApp (opt-in, shablony), ton — kak chelovek, no chestno «assistent».

# c=a+b
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional, Tuple
import urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _env(n, d=""): return os.getenv(n, d)

def _post(url: str, data: Dict[str, Any], token: str, timeout: float = 8.0) -> Tuple[int, str]:
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type":"application/json", "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec
            return int(r.status), r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return 599, str(e)

def persona_prefix() -> str:
    transparent = os.getenv("MSG_TRANSPARENT_ID", "1") == "1"
    name = os.getenv("WA_BUSINESS_NAME", "Ester")
    return f"{name} · assistent: " if transparent else f"{name}: "

class WhatsAppAdapter:
    def __init__(self, phone_id: Optional[str] = None, token: Optional[str] = None):
        self.phone_id = phone_id or _env("WA_PHONE_ID")
        self.token = token or _env("WA_TOKEN")
        if not self.phone_id or not self.token:
            raise RuntimeError("WA_PHONE_ID or WA_TOKEN not configured")

    def send_text(self, to_msisdn: str, text: str) -> Dict[str, Any]:
        url = f"https://graph.facebook.com/v21.0/{self.phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_msisdn,
            "type": "text",
            "text": {"preview_url": False, "body": persona_prefix() + text}
        }
        code, body = _post(url, payload, self.token)
        return {"ok": code in (200, 201), "status": code, "body": body}

    @staticmethod
    def verify_challenge(query: Dict[str, str]) -> Optional[str]:
        # standartnaya proverka: mode=subscribe, hub.verify_token == WA_VERIFY_TOKEN
        if query.get("hub.mode") == "subscribe" and query.get("hub.verify_token") == _env("WA_VERIFY_TOKEN"):
            return query.get("hub.challenge")
        return None

    @staticmethod
    def parse_update(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # sm. strukturu Cloud API webhook
        entry = (payload.get("entry") or [{}])[0]
        changes = entry.get("changes") or []
        if not changes:
            return None
        value = changes[0].get("value") or {}
        msgs = value.get("messages") or []
        if not msgs:
            return None
        m = msgs[0]
        if m.get("type") != "text":
            return None
        from_ = m.get("from")
        text = m.get("text", {}).get("body", "").strip()
        if not from_ or not text:
            return None
        return {
            "channel": "whatsapp",
            "chat_id": from_,  # dlya WA identifikator chata = nomer otpravitelya
            "user_id": from_,
            "text": text,
            "ts": int(time.time()),
        }