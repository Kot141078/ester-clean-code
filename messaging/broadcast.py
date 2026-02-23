# -*- coding: utf-8 -*-
"""Broadcast helper with backward-compatible signature support."""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from .outbox_store import add_outgoing


def preview_broadcast(text: str, recipients: List[str]) -> Dict[str, Any]:
    return {"ok": True, "text": text, "recipients": list(recipients), "count": len(recipients)}


def _parse_key(key: str, adapt_kind: Optional[str]) -> Tuple[str, str]:
    raw = str(key or "")
    if ":" in raw:
        channel, target = raw.split(":", 1)
        return channel.strip().lower(), target.strip()
    fallback = str(adapt_kind or "telegram").strip().lower()
    return fallback, raw


def _dryrun_send(channel: str, target: str, text: str) -> None:
    add_outgoing(
        channel,
        target,
        text,
        "ok:dryrun",
        200,
        f"dryrun:{int(time.time() * 1000)}",
    )


def _send_one(channel: str, target: str, text: str) -> bool:
    if os.getenv("DEV_DRYRUN", "0") == "1":
        _dryrun_send(channel, target, text)
        return True

    if channel == "telegram":
        try:
            from messaging.telegram_adapter import TelegramAdapter

            res = TelegramAdapter().send_message(target, text)
        except Exception:
            add_outgoing(channel, target, text, "fail", 0, "")
            return False
        add_outgoing(channel, target, text, "ok" if res.get("ok") else "fail", int(res.get("status") or 0), "")
        return bool(res.get("ok"))

    if channel == "whatsapp":
        try:
            from messaging.whatsapp_adapter import WhatsAppAdapter

            res = WhatsAppAdapter().send_text(target, text)
        except Exception:
            add_outgoing(channel, target, text, "fail", 0, "")
            return False
        add_outgoing(channel, target, text, "ok" if res.get("ok") else "fail", int(res.get("status") or 0), "")
        return bool(res.get("ok"))

    add_outgoing(channel, target, text, "skip:unsupported", 0, "")
    return False


def send_broadcast(
    arg1: List[str] | str,
    arg2: List[str] | str,
    adapt_kind: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Supported signatures:
      send_broadcast(text, recipients)
      send_broadcast(recipients, text, adapt_kind=...)
    """
    if isinstance(arg1, list):
        recipients = [str(x) for x in arg1]
        text = str(arg2)
    else:
        text = str(arg1)
        recipients = [str(x) for x in arg2] if isinstance(arg2, list) else [str(arg2)]

    sent = 0
    skipped = 0
    for key in recipients:
        channel, target = _parse_key(key, adapt_kind)
        if _send_one(channel, target, text):
            sent += 1
        else:
            skipped += 1

    return {"ok": True, "sent": sent, "skipped": skipped, "count": len(recipients)}
