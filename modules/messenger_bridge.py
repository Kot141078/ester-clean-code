# -*- coding: utf-8 -*-
"""
modules/messenger_bridge.py — Unifitsirovannyy most dlya messendzherov.

Mosty:
- (Yavnyy) Edinyy interfeys send_text() dlya WA; Telegram uzhe realizovan v proekte.
- (Skrytyy #1) A/B-slot proaktivnosti (MSG_STYLE_AB=A|B) — bezopasnoe usilenie «chelovechnosti».
- (Skrytyy #2) Bystryy avtokatbek: esli vneshniy API nedostupen — myagkiy otkaz i dry echo.

Zemnoy abzats:
Daet Ester prostoy vyzov «otpravit cheloveku tekst» s korrektnoy formalizatsiey,
ne lomaya tekuschikh routov Telegram; WA dobavlyaetsya kak drop-in.

# c=a+b
"""
from __future__ import annotations
import os
import json
import time
from typing import Tuple, Dict, Any, Optional

import urllib.request
import urllib.error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MSG_STYLE_AB = os.environ.get("MSG_STYLE_AB", os.environ.get("MSG_STYLE_FALLBACK", "A")).upper().strip() or "A"


class WhatsAppSender:
    """
    Obertka nad WA Cloud API.
    Variant A (po umolchaniyu): esli net tokena/ID — vsegda dry-run; zapros naruzhu ne ukhodit.
    Variant B: probovat skhodit naruzhu, no padat myagko, vozvraschaya echo.
    """
    def __init__(self, access_token: str, phone_number_id: str, timeout: float = 6.0):
        self.access_token = (access_token or "").strip()
        self.phone_number_id = (phone_number_id or "").strip()
        self.timeout = float(timeout or 6.0)

    def _post_json(self, url: str, obj: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        data = json.dumps(obj).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                txt = resp.read().decode("utf-8", "ignore")
                try:
                    j = json.loads(txt)
                except Exception:
                    j = {"raw": txt}
                return True, j
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore") if hasattr(e, "read") else ""
            return False, {"http": e.code, "body": body}
        except Exception as e:
            return False, {"error": str(e)}

    def send_text(self, to: str, text: str, dry_run: bool = False) -> Tuple[bool, Dict[str, Any]]:
        """
        Vozvraschaet (ok, result). Nikogda ne brosaet isklyucheniy vverkh.
        """
        if dry_run or not (self.access_token and self.phone_number_id):
            # Echo-put bez vneshnikh effektov.
            return True, {
                "mode": "dry",
                "to": to,
                "text": text,
                "ts": int(time.time()),
                "ab": MSG_STYLE_AB,
            }

        url = f"https://graph.facebook.com/v19.0/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }

        ok, res = self._post_json(url, payload)
        if not ok and MSG_STYLE_AB == "B":
            # Myagkiy avtokatbek (B): replitsiruem kak dry
            return True, {
                "mode": "fallback-dry",
                "to": to,
                "text": text,
                "result": res,
                "ts": int(time.time()),
                "ab": MSG_STYLE_AB,
            }
        return ok, res