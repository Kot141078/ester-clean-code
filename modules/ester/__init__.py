from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
"""Paket Ester: sluzhebnye utility i status.

Mosty:
- Yavnyy: (app.py ↔ sluzhebnye moduli) — akkuratnaya tochka vkhoda dlya integratsiy.
- Skrytyy #1: (Diagnostika ↔ Myshlenie) — zdes zhivut status/manifest.
- Skrytyy #2: (ENV ↔ Dokumentatsiya) — vspomogatelnye funktsii chitayut okruzhenie.

Zemnoy abzats:
Importiruya modules.ester, inzhener poluchaet dostup k statusu rezhimov Ester
bez vmeshatelstva v thinking/* i yadro pamyati.
# c=a+b
"""