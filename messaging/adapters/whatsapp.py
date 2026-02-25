# -*- coding: utf-8 -*-
"""messaging/adapters/whatsapp.py - otpravka v WhatsApp Business Cloud API.

MOSTY:
- (Yavnyy) send_text(to, text) → dict {sent,skipped,http_status,...}; podderzhivaet wa_id or telefon (E.164).
- (Skrytyy #1) Logi v outbox → sovmestimost s retrayami.
- (Skrytyy #2) Bazovye oshibki shablonov/24-hour okna fiksiruyutsya dlya diagnostiki v outbox.raw_json.

ZEMNOY ABZATs:
Ofitsialnyy kanal WhatsApp: akkuratno, s uchetom ogranicheniy (24 hours/shablony) i bez “robota” v imeni kontakta.

# c=a+b"""
from __future__ import annotations

import json, os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from typing import Dict, Any

from messaging.outbox_store import record_attempt
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

GRAPH = os.getenv("WHATSAPP_GRAPH_BASE", "https://graph.facebook.com/v20.0").rstrip("/")
PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID","")
TOKEN = os.getenv("WHATSAPP_TOKEN","")

def _call(path: str, payload: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
    if not (PHONE_ID and TOKEN):
        return (0, {"ok": False, "error": "no phone_id or token"})
    url = f"{GRAPH}/{PHONE_ID}/{path.lstrip('/')}"
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type":"application/json","Authorization":f"Bearer {TOKEN}"})
    try:
        with urlopen(req, timeout=10) as r:
            return (int(r.getcode()), json.loads(r.read().decode("utf-8") or "{}"))
    except HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            data = {"error": {"message": str(e)}}
        return (int(e.code), data)
    except URLError as e:
        return (0, {"error": {"message": str(e)}})

def send_text(to: str, text: str) -> Dict[str, Any]:
    channel = "whatsapp"
    payload = {
        "messaging_product": "whatsapp",
        "to": to.replace("whatsapp:", "").replace("+","").strip(),
        "type": "text",
        "text": {"preview_url": False, "body": text}
    }
    code, data = _call("messages", payload)
    ok = 200 <= code < 300 and isinstance(data.get("messages"), list)
    msg_id = ""
    if ok:
        try:
            msg_id = str(data["messages"][0]["id"])
        except Exception:
            msg_id = ""
    record_attempt(channel, payload["to"], text, code, "ok" if ok else "fail", msg_id, data)
    return {"sent": 1 if ok else 0, "skipped": 0 if ok else 1, "http_status": code, "message_id": msg_id, "raw": data}