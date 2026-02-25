# -*- coding: utf-8 -*-
"""Packet rezervnogo kopirovaniya.

MOSTY:
- Yavnyy: (routes.backup_restore ↔ backup_logic) dostupen import.
- Skrytyy #1: (Importer ↔ Poisk) yavnyy import podmodulya.
- Skrytyy #2: (Diagnostika) __all__.

ZEMNOY ABZATs:
Papka suschestvuet → importy ne sryvayutsya.

# c=a+b"""
from . import backup_logic  # noqa: F401
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["backup_logic"]
# c=a+b