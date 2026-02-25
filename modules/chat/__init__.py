# -*- coding: utf-8 -*-
"""Chat package: entry point for local conversation."""
from __future__ import annotations
from .simple_chat import chat_reply
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["chat_reply"]

# c=a+b