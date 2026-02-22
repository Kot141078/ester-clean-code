
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules/listeners — psevdopaket s avto-poiskom project root,
gde lezhit realnaya papka `listeners/`.

Mosty:
- Yavnyy: (Importy ↔ FS) — import `modules.listeners` otdaet top-level `listeners`.
- Skrytyy #1: (DX ↔ Nadezhnost) — esli modul vyzyvayut iz podpapki, my naydem koren i dobavim ego v sys.path.
- Skrytyy #2: (Setevoe telo ↔ Drayvery) — bez dubley koda.

Zemnoy abzats:
Zapusk iz «vnutrenney» papki lomaet PYTHONPATH, i `listeners` ne viden.
My podnimaemsya vverkh po derevu i dobavlyaem put, gde est `listeners/`.
# c=a+b
"""
import importlib, sys, pathlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _import_listeners():
    # 1) Pryamaya popytka
    try:
        return importlib.import_module("listeners")
    except Exception:
        pass
    # 2) Poisk vverkh ot tekuschego fayla
    here = pathlib.Path(__file__).resolve()
    for parent in list(here.parents)[:8]:  # podnimaemsya do 8 urovney
        if (parent.parent / "listeners").is_dir():
            root = str(parent.parent)
            if root not in sys.path:
                sys.path.insert(0, root)
            return importlib.import_module("listeners")
        if (parent / "listeners").is_dir():
            root = str(parent)
            if root not in sys.path:
                sys.path.insert(0, root)
            return importlib.import_module("listeners")
    # 3) Finalnyy folbek: informativnaya oshibka
    raise ModuleNotFoundError("Cannot locate top-level 'listeners/' directory for modules.listeners")

_listeners = _import_listeners()
# Probrasyvaem modul 'listeners' v prostranstvo imen 'modules.listeners'
sys.modules[__name__] = _listeners  # type: ignore