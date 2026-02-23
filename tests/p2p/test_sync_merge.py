# -*- coding: utf-8 -*-
from crdt.lww_set import LwwSet
from crdt.types import Item
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_merge_idempotent_and_commutative():
    a = LwwSet("A")
    b = LwwSet("B")
    c = LwwSet("C")
    a.add(Item("x", {"n": 1}))
    b.add(Item("y", {"n": 2}))
    c.add(Item("z", {"n": 3}))
    a.merge(b)
    a.merge(c)
    c.merge(a)
    b.merge(c)
    # teper u vsekh troikh odinakovoe vidimoe mnozhestvo
    va = set(a.visible_items().keys())
    vb = set(b.visible_items().keys())
    vc = set(c.visible_items().keys())
# assert va == vb == vc == {"x", "y", "z"}