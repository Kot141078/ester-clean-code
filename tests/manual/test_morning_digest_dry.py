# -*- coding: utf-8 -*-
from __future__ import annotations

# --- bootstrap: ensure project root on sys.path ---
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# --- end bootstrap ---

"""
Dry-run MorningDigestDaemon: forsiruem utro i otpravku.
Zapusk:
    # iz kornya proekta
    $env:PYTHONPATH = (Get-Location).Path
    python tests\manual\test_morning_digest_dry.py
"""

import types

TEST_USER = "Owner"


# --- Zaglushka MemoryManager ---
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


import proactive_notifier as pn
from proactive_notifier import MorningDigestDaemon
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# ----- MONKI-PATChI -----
# 1) Vsegda est "chat"
def fake_get_chat_id(self, user: str):
    return 999999999


# 2) We consider that now is the “morning window”
def fake_now_in_morning_window(self):
    return True


# 3) Replaces sending to Telegram with printing
def fake_tg_send(token: str, chat_id: int, text: str):
    print("\n=== [DRY-RUN] Telegram message would be ===")
    print(f"token: {token[:5]}... (masked)")
    print(f"chat_id: {chat_id}")
    print("----- TEXT START -----")
    print(text)
    print("----- TEXT END -----")
    return True


pn.tg_send = fake_tg_send


def main():
    mm = FakeMM(size=120, emotions={"anxiety": 0.42, "interest": 0.68})
    daemon = MorningDigestDaemon(mm, providers=None, tg_token="TEST_TOKEN", default_user=TEST_USER)

    # Podkruchivaem metody
    daemon._get_chat_id = types.MethodType(fake_get_chat_id, daemon)
    daemon._now_in_morning_window = types.MethodType(fake_now_in_morning_window, daemon)

    daemon._tick()  # odin tik → pechat v konsol


if __name__ == "__main__":
    main()
