# -*- coding: utf-8 -*-
"""Telegram adapter used by messaging tests and outbox resend logic."""
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _post(url: str, data: Dict[str, Any], timeout: float = 8.0) -> Tuple[int, str]:
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            return int(resp.status), resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:  # pragma: no cover - network errors are environment-specific
        return 599, str(exc)


def persona_prefix() -> str:
    transparent = _env("MSG_TRANSPARENT_ID", "1") == "1"
    name = _env("TG_BOT_NAME", "Ester")
    return f"{name} · assistent: " if transparent else f"{name}: "


class TelegramAdapter:
    def __init__(self, token: Optional[str] = None):
        self.token = token or _env("TG_BOT_TOKEN") or _env("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise RuntimeError("TG_BOT_TOKEN/TELEGRAM_BOT_TOKEN not configured")

    def send_message(self, chat_id: Any, text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data: Dict[str, Any] = {"chat_id": chat_id, "text": persona_prefix() + str(text)}
        if parse_mode:
            data["parse_mode"] = parse_mode
        code, body = _post(url, data)
        return {"ok": code in (200, 201), "status": code, "body": body}

    @staticmethod
    def parse_update(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        msg = (payload or {}).get("message") or {}
        chat = msg.get("chat") or {}
        frm = msg.get("from") or {}
        text = (msg.get("text") or "").strip()
        chat_id = chat.get("id")
        if not text or chat_id is None:
            return None
        return {
            "channel": "telegram",
            "chat_id": chat_id,
            "user_id": frm.get("id"),
            "text": text,
            "ts": int(msg.get("date") or time.time()),
        }

