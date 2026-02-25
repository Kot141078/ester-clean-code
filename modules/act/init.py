# -*- coding: utf-8 -*-
"""Paket deystviy (act).

MOSTY:
- Yavnyy: (routes.agent_run_routes ↔ ispolnitel) reeksport runner.
- Skrytyy #1: (Importer ↔ Ustoychivost) nalichie __all__ i yavnogo importa isklyuchaet padeniya avtopoiska.
- Skrytyy #2: (Diagnostika ↔ Prostota) status available via runner.status().

ZEMNOY ABZATs:
This is “papka s instrumentami”, a ne odna otvertka - vazhno, chtoby papka suschestvovala.

# c=a+b"""
from . import runner  # noqa: F401
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["runner"]
# c=a+b