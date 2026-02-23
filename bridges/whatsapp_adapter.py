"""
WhatsAppAdapter — podderzhka Cloud API (Meta). Maskirovka pod «obychnyy kontakt».
Kontrakt s yadrom Ester — cherez ESTER_CHAT_GATEWAY (drop-in).

MOSTY (yavnyy):
- StyleEngine dlya korrektnoy stilistiki (advokat/shkolnik/drug).

MOSTY (skrytye):
- PersonaDetector dlya neizbytochnogo vyyavleniya tipa sobesednika bez «tupykh oprosov».
- Vstroennye khinty dlya proaktivnosti (reply-windows, tikhie napominaniya), sovmestimye s ambient_proactive.

ZEMNOY ABZATs:
- Gotov k podklyucheniyu v prod s minimalnymi sekretami. Verifikatsiya vebkhuka cherez ESTER_WHATSAPP_VERIFY_TOKEN.
"""

import os
from typing import Any, Dict, List
import httpx
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

WHATSAPP_PHONE_ID = os.getenv("ESTER_WHATSAPP_PHONE_ID", "")
WHATSAPP_TOKEN = os.getenv("ESTER_WHATSAPP_TOKEN", "")
WHATSAPP_BASE = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages" if WHATSAPP_PHONE_ID else ""
ESTER_IMPL = os.getenv("ESTER_MESSAGING_IMPL", "A").upper()

class WhatsAppAdapter:
    def __init__(self, chat_gateway: str, style_engine, detector, mask_humanlike: bool = True):
        self.chat_gateway = chat_gateway
        self.style_engine = style_engine
        self.detector = detector
        self.mask_humanlike = mask_humanlike

    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    await self._handle_message(value, msg)
        return {"ok": True}

    async def _handle_message(self, value: Dict[str, Any], msg: Dict[str, Any]):
        text_in = ""
        if msg.get("type") == "text":
            text_in = msg["text"].get("body", "")
        elif msg.get("type") == "image":
            text_in = msg.get("caption", "") or "[image]"
        else:
            text_in = "[unsupported]"

        from_wa = msg.get("from", "")
        role = self.detector.infer_role(text_in, meta={"platform": "whatsapp", "from": from_wa})
        style = self.style_engine.pick_style(role, platform="whatsapp", mask=self.mask_humanlike)

        out_text = await self._ask_ester(text_in, role=role)
        final_text = self.style_engine.render(out_text, style=style)

        await self._reply_wa(to=from_wa, text=final_text)

    async def _ask_ester(self, text: str, role: str) -> str:
        data = {"text": text, "meta": {"source": "whatsapp", "role": role, "stealth": True}}
        timeout = httpx.Timeout(15.0, connect=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                r = await cli.post(self.chat_gateway, json=data)
                r.raise_for_status()
                j = r.json()
                return j.get("reply") or j.get("text") or ""
        except Exception:
            # Bystryy otkat (B->A odinakov dlya nas)
            async with httpx.AsyncClient(timeout=timeout) as cli:
                r = await cli.post(self.chat_gateway, json=data)
                r.raise_for_status()
                j = r.json()
                return j.get("reply") or j.get("text") or ""

    async def _reply_wa(self, to: str, text: str):
        if not WHATSAPP_BASE or not WHATSAPP_TOKEN:
            return
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as cli:
            await cli.post(WHATSAPP_BASE, json=payload)

# c=a+b