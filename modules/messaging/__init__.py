
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules/messaging — psevdopaket s avto-poiskom project root,
gde lezhit realnaya papka `messaging/`.

Mosty:
- Yavnyy: (Importy ↔ I/O) — import `modules.messaging` otdaet top-level `messaging`.
- Skrytyy #1: (DX ↔ Nadezhnost) — esli modul vyzyvayut iz podpapki, my naydem koren i dobavim ego v sys.path.
- Skrytyy #2: (Memory ↔ Kanaly) — konsolidiruem tochki vkhoda.

Zemnoy abzats:
Zapusk iz «vnutrenney» papki lomaet PYTHONPATH, i `messaging` ne viden.
My podnimaemsya vverkh po derevu i dobavlyaem put, gde est `messaging/`.
# c=a+b
"""
import importlib, sys, pathlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _import_messaging():
    try:
        return importlib.import_module("messaging")
    except Exception:
        pass
    here = pathlib.Path(__file__).resolve()
    for parent in list(here.parents)[:8]:
        if (parent.parent / "messaging").is_dir():
            root = str(parent.parent)
            if root not in sys.path:
                sys.path.insert(0, root)
            return importlib.import_module("messaging")
        if (parent / "messaging").is_dir():
            root = str(parent)
            if root not in sys.path:
                sys.path.insert(0, root)
            return importlib.import_module("messaging")
    raise ModuleNotFoundError("Cannot locate top-level 'messaging/' directory for modules.messaging")

_messaging = _import_messaging()
sys.modules[__name__] = _messaging  # type: ignore