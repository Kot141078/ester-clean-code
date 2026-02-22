# -*- coding: utf-8 -*-
"""
Paket selfmanage (shim).

MOSTY:
- Yavnyy: (routes.backup_and_clone ↔ backup_settings) importiruemaya tochka.
- Skrytyy #1: (Status ↔ Diagnostika) minimum API dostupen.
- Skrytyy #2: (Importer ↔ Nadezhnost) __all__.

ZEMNOY ABZATs:
Paket suschestvuet, importy prokhodyat.

# c=a+b
"""
from . import backup_settings  # noqa: F401
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["backup_settings"]
# c=a+b