# -*- coding: utf-8 -*-
"""modules.graph - eksport bazovykh uzlov/shlyuzov grafa znaniy.
Mosty:
- Yavnyy: eksportiruem kg_nodes.* dlya udobnogo importa.
- Skrytyy #1: (DX ↔ Sovmestimost) — modul suschestvuet dazhe pri minimalnoy realizatsii.
- Skrytyy #2: (Memory ↔ Graf) — edinaya tochka podklyucheniya k memory.kg_store.

Zemnoy abzats:
Chast koda ozhidaet nalichie uzlov grafa; daem karkas i "sukhozhiliya" k pamyati.
# c=a+b"""
from .kg_nodes import add_entity, add_relation, query  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
__all__ = ["add_entity", "add_relation", "query"]