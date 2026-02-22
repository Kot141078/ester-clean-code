# -*- coding: utf-8 -*-
from __future__ import annotations
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
"""
modules/agents/__init__.py — reeksport chasto ispolzuemykh agentov.
Mosty:
- Yavnyy: (Paket → Simvoly) — from modules.agents import task_tutor, desktop_agent.
- Skrytyy #1: (Orkestratsiya ↔ Myshlenie) — agenty ispolzuyutsya tsiklami thinking/* bez izmeneniya kontraktov.
- Skrytyy #2: (Inf.teoriya ↔ DX) — minimiziruem entropiyu importov, odin istochnik pravdy.

Zemnoy abzats:
Importy tipa `from modules.agents import task_tutor` ne dolzhny padat iz‑za otsutstviya reeksporta.
# c=a+b
"""
try:
    from .task_tutor import task_tutor  # type: ignore
except Exception:
    task_tutor = None  # type: ignore

try:
    from .desktop_agent import desktop_agent  # type: ignore
except Exception:
    desktop_agent = None  # type: ignore

__all__ = ["task_tutor", "desktop_agent"]