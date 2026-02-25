from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -*- coding: utf-8 -*-
"""quality - top-level most dlya podsistemy quality.
Mosty:
- Yavnyy: predostavlyaet modul guard s funktsiey enable(), esli ee net v realnoy realizatsii.
- Skrytyy #1: (Bezopasnost ↔ DX) — ne daem upast importam iz-za otsutstvuyuschego simvola.
- Skrytyy #2: (Payplayn ↔ UI) — edinaya tochka vklyucheniya gvardov.

Zemnoy abzats:
Nekotorye logi zvali `from modules.quality.guard import enable`, a v module ne bylo takogo simvola.
Here we go sovmestimuyu realizatsiyu.
# c=a+b"""