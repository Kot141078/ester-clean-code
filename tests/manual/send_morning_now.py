# -*- coding: utf-8 -*-
from __future__ import annotations

import os

# --- bootstrap: ensure project root on sys.path ---
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# --- end bootstrap ---

"""Boevoy vystrel utrennego daydzhesta “pryamo seychas”.
Trebuetsya: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID (v okruzhenii).
Zapusk (PowerShell):
    $env:PYTHONPATH = (Get-Location).Path
    $env:TELEGRAM_TOKEN = "XXX:telegram_bot_token"
    $env:TELEGRAM_CHAT_ID = "123456789"
    python tests\manual\send_morning_now.py"""

import types

from proactive_notifier import MorningDigestDaemon
from telegram_bot import (  # ispolzuem realnuyu otpravku
    send_text as tg_send,
)
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# --- Mini plugs for mm (enough for digest) ---
class FakeVStore:
    def __init__(self, size: int):
        self.size = size


class FakeMM:
    def __init__(self, size: int, emotions):
        self.vstore = FakeVStore(size)
        self._meta = {}
        self._emotions = emotions

    def get_session_meta(self, user: str, key: str):
        return self._meta.get((user, key), {}).copy()

    def set_session_meta(self, user: str, key: str, value):
        self._meta[(user, key)] = dict(value)

    def get_emotions_journal(self, user: str, n: int = 1):
        return [{"emotions": self._emotions}]


# --- Konfig okruzheniya ---
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
USER = os.environ.get("ESTER_DEFAULT_USER", "Owner")

if not TOKEN or not CHAT_ID:
    raise SystemExit("You need to set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID")


def main():
    # Substituting real/desired values
    fake_store_size = 120
    fake_emotions = {"anxiety": 0.28, "interest": 0.62}

    mm = FakeMM(fake_store_size, fake_emotions)
    daemon = MorningDigestDaemon(mm, providers=None, tg_token=TOKEN, default_user=USER)

    # 1) force the availability of chat
    def _get_chat_id(self, user: str):
        return int(CHAT_ID)

    daemon._get_chat_id = types.MethodType(_get_chat_id, daemon)

    # 2) we believe that right now it’s “morning”
    def _now_in_morning_window(self):
        return True

    daemon._now_in_morning_window = types.MethodType(_now_in_morning_window, daemon)

    # 3) use real tg_send - it is imported into the daemon as mon.tg_send
    # We don’t patch anything, let it send for real.

    # 4) tik → soobschenie uydet v tvoy Telegram odin raz (metka "segodnya uzhe otpravlyali" sokhranitsya)
    daemon._tick()
    print(
        "✓ Message sent (if everything is ok with the token/chat)."
    )


if __name__ == "__main__":
    main()
