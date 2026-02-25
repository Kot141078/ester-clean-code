# -*- coding: utf-8 -*-
"""modules/context/web_adapter.py - adapter dlya obscheniya cherez web-interfeys.

Perekhvatyvaet repliki polzovatelya i otvety Ester
(pri proksirovanii chata ili REST-zaprosakh) i zapisyvaet v pamyat.

# c=a+b"""
from modules.context.adapters import log_context
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def record_user_message(text: str) -> None:
    log_context("web", "dialog", text, {"from": "user"})

def record_ester_reply(text: str) -> None:
    log_context("web", "dialog", text, {"from": "ester"})