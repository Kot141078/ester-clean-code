# -*- coding: utf-8 -*-
"""
messaging/dispatcher.py — dispetcher, komandy, tishina, proaktivnost (persistentnaya).

MOSTY:
- (Yavnyy) /start|/stop|/silence [30m|2h|1d]|/resume|/help; opt-in/tishina/limity — cherez SQLite-khranilische.
- (Skrytyy #1) Politiki: opt-in obyazatelen (esli vklyucheno), «tikhiy rezhim» uchityvaetsya v proaktivke i otvetakh.
- (Skrytyy #2) Render teksta cherez author_text + persona iz prefs; padeniy net dazhe bez nastroek.

ZEMNOY ABZATs:
Pishem, kak chelovek, no po pravilam: ne navyazyvaemsya, uvazhaem tishinu i chastotu, vsegda mozhno postavit «na pauzu».

# c=a+b
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Dict, Optional

from nl.authoring_router import author_text
from messaging.optin_store import (
    set_optin,
    get_optin,
    set_prefs,
    get_prefs,
    record_outbound,
    last_outbound,
    set_silence_until,
    clear_silence,
    get_silence_until,
)

_RE_DUR = re.compile(r"^\s*(\d+)\s*([mhd])?\s*$", re.I)

def _envb(name: str, default: bool=True) -> bool:
    v = (os.getenv(name, "1" if default else "0") or "").lower()
    return v in ("1","true","on","yes")

def _silence_default_min() -> int:
    try:
        return max(1, int(os.getenv("SILENCE_DEFAULT_MIN", "60")))
    except Exception:
        return 60

def _silence_max_h() -> int:
    try:
        return max(1, int(os.getenv("SILENCE_MAX_HOURS", "48")))
    except Exception:
        return 48

def _parse_duration_to_seconds(s: str | None) -> int:
    if not s:
        return _silence_default_min() * 60
    m = _RE_DUR.match(s)
    if not m:
        return _silence_default_min() * 60
    val = int(m.group(1))
    unit = (m.group(2) or "m").lower()
    if unit == "m":
        sec = val * 60
    elif unit == "h":
        sec = val * 3600
    else:
        sec = val * 86400
    max_sec = _silence_max_h() * 3600
    return int(min(max_sec, max(60, sec)))

@dataclass
class InEvent:
    channel: str  # telegram | whatsapp
    chat_id: str
    user_id: str
    text: str
    ts: int

def register_optin(key: str, agree: bool = True) -> None:
    set_optin(key, agree)

def _can_proactive(key: str) -> bool:
    if _envb("MSG_OPTIN_REQUIRED", True) and not get_optin(key):
        return False
    # silence
    if get_silence_until(key) > time.time():
        return False
    rate = get_prefs(key).rate_per_h
    if rate <= 0:
        return False
    last = last_outbound(key)
    if (time.time() - last) < (3600.0 / max(1, rate)):
        return False
    return True

def record_outbound_key(key: str) -> None:
    record_outbound(key)

def _key(evt: InEvent) -> str:
    return f"{evt.channel}:{evt.chat_id}"

def _reply(txt: str, kind: str = "friend") -> str:
    return author_text(txt, recipient_kind=kind)

def _silence_reply(minutes: int) -> str:
    return _reply(f"Vklyuchayu tikhiy rezhim na {minutes} min. Chtoby vernutsya — napishite «/resume».", "friend")

def _resume_reply() -> str:
    return _reply("Tikhiy rezhim otklyuchen. Ya na svyazi.", "friend")

def _help_reply() -> str:
    return _reply("Komandy: /start — podklyuchit, /stop — otpiska, /silence [30m|2h|1d] — tishe, /resume — vernutsya, /help — spravka.", "friend")

def accept_incoming(evt: InEvent) -> Dict[str, str]:
    """
    Normalizuem vkhodyaschie; komandy obrabatyvaem zdes.
    Vozvraschaet {action: welcome|optout|silence|resume|help|forward, reply?: text}
    """
    key = _key(evt)
    text = (evt.text or "").strip()

    if text.lower() in ("/start", "start", "start"):
        register_optin(key, True)
        return {"action": "welcome", "reply": _reply("Spasibo, chto podklyuchili menya. Chem mogu pomoch pryamo seychas?", "friend")}

    if text.lower() in ("stop", "otpiska", "stop", "/stop"):
        register_optin(key, False)
        clear_silence(key)
        return {"action": "optout", "reply": _reply("Otklyuchayu uvedomleniya. Esli peredumaete — napishite «/start».", "friend")}

    # /silence [dur]
    if text.lower().startswith("/silence") or text.lower().startswith("tikho"):
        parts = text.split(maxsplit=1)
        dur = parts[1] if len(parts) > 1 else None
        sec = _parse_duration_to_seconds(dur)
        until = time.time() + sec
        set_silence_until(key, until)
        return {"action": "silence", "reply": _silence_reply(int(sec/60))}

    if text.lower() in ("/resume", "resume", "vozobnovit"):
        clear_silence(key)
        return {"action": "resume", "reply": _resume_reply()}

    if text.lower() in ("/help", "help", "spravka"):
        return {"action": "help", "reply": _help_reply()}

    return {"action": "forward"}

def maybe_proactive(key: str, intent: str, recipient_kind: str = "friend") -> Optional[str]:
    """Reshaem, mozhno li prislat proaktivnoe soobschenie po sobytiyu (uchet tishiny/opt-in/limitov)."""
    if not _envb("MSG_PROACTIVE_ENABLE", True):
        return None
    if not _can_proactive(key):
        return None
    txt = author_text(intent, recipient_kind=recipient_kind)
    record_outbound(key)
    return txt
