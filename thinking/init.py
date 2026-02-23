# -*- coding: utf-8 -*-
"""
Paket-most `thinking` → `modules.thinking`.

MOSTY:
- Yavnyy: (routes.chat_routes i dr. ↔ yadro) re-export think, THINKER.
- Skrytyy #1: (Sovmestimost ↔ Puti) import po staromu puti `thinking.*` ne lomaetsya.
- Skrytyy #2: (Gibkost ↔ Delegirovanie) fakticheskaya logika zhivet v modules.thinking.

ZEMNOY ABZATs:
Routy, napisannye pod `thinking.*`, bolshe ne padayut na importe — vse prozrachnym obrazom prikhodit iz `modules.thinking`.

# c=a+b
"""
from __future__ import annotations
from . import think_core as _core
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

think = _core.think
THINKER = _core.THINKER

__all__ = ["think", "THINKER"]
# c=a+b