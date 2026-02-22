# -*- coding: utf-8 -*-
"""
Paket chat: tochka vkhoda dlya lokalnogo dialoga.
"""
from __future__ import annotations
from .simple_chat import chat_reply
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["chat_reply"]

# c=a+b