# -*- coding: utf-8 -*-
"""
modules/context/adapters.py — universalnyy adapter konteksta dlya pamyati Ester.

Funktsiya log_context(source, type_, text, meta)
  → avtomaticheski sokhranyaet sobytie obscheniya, fayla ili mysli v pamyat.

Ispolzuetsya vo vsekh adapterakh.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def log_context(source: str, type_: str, text: str, meta: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Universalnyy logger konteksta:
      source — "web" | "telegram" | "file" | "thought"
      type_  — "dialog" | "fact" | "goal" | "dream"
    """
    meta = meta or {}
    meta["source"] = source
    meta["length"] = len(text)
    return memory_add(type_, text, meta)