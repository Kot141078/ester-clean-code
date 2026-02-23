from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
"""
tools — paket utilit Ester.
Mosty:
- Yavnyy: (CLI ↔ Moduli) — pozvolyaet vyzyvat utility kak pakety cherez `python -m tools.*`.
- Skrytyy #1: (DX ↔ Nadezhnost) — predskazuemaya zagruzka v raznykh rezhimakh zapuska.
- Skrytyy #2: (Testy ↔ CI) — odinakovyy import v lokali i na CI.

Zemnoy abzats:
Nalichie __init__.py ustranyaet raskhozhdeniya importa mezhdu rezhimami `-m` i zapuskom .py faylov.
# c=a+b
"""