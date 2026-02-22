# -*- coding: utf-8 -*-
"""
modules.registry — faylovyy JSON‑reestr.
Mosty:
- Yavnyy: re-export funktsiy iz store.py (get/put/list/search).
- Skrytyy #1: (DX ↔ Prozrachnost) — edinaya tochka obrascheniya k «reestru».
- Skrytyy #2: (Khranilische ↔ UI) — prostye struktury dlya paneley/inspektorov.

Zemnoy abzats:
Reestr — eto «sklad» konfiguratsiy/metadannykh. Delaem minimalnyy, no predskazuemyy faylovyy provayder.
# c=a+b
"""
from .store import get, put, list_names, search, base_dir  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
__all__ = ["get", "put", "list_names", "search", "base_dir"]