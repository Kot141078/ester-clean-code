# -*- coding: utf-8 -*-
"""actions_discovery.py (root wrapper)

U tebya dva fayla s odnim imenem:
  - <root>/actions_discovery.py
  - <root>/modules/thinking/actions_discovery.py

Esli ostavit oba “tolstymi”, import budet nepredskazuemym (what pervym v sys.path - to i pobedilo).
This fayl delaet kornevoy actions_discovery bezopasnym: on prosto reeksportiruet kanonicheskuyu realizatsiyu.

Rekomenduemoe: derzhat logiku v modules/thinking/actions_discovery.py, and v korne - tolko etot wrapper."""

from __future__ import annotations

from modules.thinking.actions_discovery import discover_actions  # noqa: F401
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["discover_actions"]