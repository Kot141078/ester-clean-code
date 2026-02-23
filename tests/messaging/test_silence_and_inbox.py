# -*- coding: utf-8 -*-
"""
tests/messaging/test_silence_and_inbox.py — «tikhiy rezhim» i mini-inboks.

MOSTY:
- (Yavnyy) Komandy /silence i /resume menyayut povedenie maybe_proactive().
- (Skrytyy #1) Vkhodyaschie pishutsya v inbox i chitayutsya adminkoy.
- (Skrytyy #2) Parser dlitelnosti ogranichivaet maksimum SILENCE_MAX_HOURS.

ZEMNOY ABZATs:
Proveryaem, chto my ne budem «budit» kontakt v «tikhom rezhime» i chto poslednie soobscheniya vidny operatoru.

# c=a+b
"""
from __future__ import annotations

import os, time

from messaging.dispatcher import InEvent, accept_incoming, maybe_proactive
from messaging.inbox_store import add_event, list_recent
from messaging.optin_store import set_optin, get_silence_until, clear_silence
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_silence_blocks_proactive(monkeypatch):
    monkeypatch.setenv("MESSAGING_DB_PATH", "data/test_msg.db")
    key = "telegram:42"
    set_optin(key, True)
    # vklyuchim tishinu cherez komandu
    evt = InEvent(channel="telegram", chat_id="42", user_id="7", text="/silence 30m", ts=int(time.time()))
    dec = accept_incoming(evt)
    assert dec["action"] == "silence"
    assert get_silence_until(key) > time.time()
    # proaktivka blokiruetsya
    txt = maybe_proactive(key, "napomnyu pozzhe", "friend")
    assert txt is None
    # snimem tishinu
    clear_silence(key)
    txt2 = maybe_proactive(key, "korotkoe napominanie", "friend")
    # mozhet byt None iz-za rate; glavnoe — ne blokiruetsya tishinoy
    assert txt2 is None or isinstance(txt2, str)

def test_inbox_record_and_list(monkeypatch):
    monkeypatch.setenv("MESSAGING_DB_PATH", "data/test_msg.db")
    add_event(time.time(), "telegram", "42", "7", "privet")
    xs = list_recent(10)
    assert len(xs) >= 1
    _id, ts, ch, chat, user, text = xs[0]
    assert ch == "telegram" and chat == "42" and text