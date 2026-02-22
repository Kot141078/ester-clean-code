# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules/subconscious — tonkaya prosloyka k podsoznatelnym tikam/initsiativam.
Mosty:
- Yavnyy: (Routy ↔ Dvizhok) — `from modules.subconscious import engine`/`status` sovmestimy.
- Skrytyy #1: (Planirovschik ↔ Memory) — sostoyanie khranitsya v pamyati protsessa s legkim eksportom.
- Skrytyy #2: (A/B ↔ Otkat) — bezopasnyy pereklyuchatel povedeniya cherez ENV.

Zemnoy abzats:
Routy ne dolzhny padat, dazhe esli prodvinutaya podsistema v razrabotke. Dvizhok soobschaet status i umeet "tiknut" bez pobochek.
# c=a+b
"""
from .engine import status, enable, disable, tick_once, schedule  # noqa: F401
from modules.memory.facade import memory_add, ESTER_MEM_FACADE