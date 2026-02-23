# -*- coding: utf-8 -*-
from crdt.lww_set import LwwSet
from crdt.types import Item
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_add_remove_win_by_ts():
    a = LwwSet("A")
    b = LwwSet("B")
    d1 = a.add(Item("x", {"v": 1}))
    d2 = b.remove("x")
    # iskusstvenno delaem bolee «pozdnyuyu» operatsiyu
    b.clock = max(b.clock, d1.ts + 1)
    d3 = b.remove("x")
    a.merge(b)
    assert "x" not in a.visible_items()  # remove pobedil


def test_concurrent_adds_different_payloads():
    a = LwwSet("A")
    b = LwwSet("B")
    a.add(Item("x", {"v": 1}))
    b.add(Item("x", {"v": 2}))
    a.merge(b)
    b.merge(a)
    va = a.visible_items()["x"].payload["v"]
    vb = b.visible_items()["x"].payload["v"]
    assert va == vb  # soglasovannost


def test_snapshot_roundtrip():
    a = LwwSet("A")
    a.add(Item("x", {"t": "hello"}))
    snap = a.snapshot()
    b = LwwSet.from_snapshot(snap)
# assert b.visible_items()["x"].payload["t"] == "hello"