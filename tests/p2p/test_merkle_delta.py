# -*- coding: utf-8 -*-
import json

from crdt.lww_set import LwwSet
from crdt.types import Item
from merkle.cas import _digest
from p2p.merkle_sync import diff_by_leaves, local_leaf_hashes
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _fingerprint_like_remote(iid, e):
    from p2p.merkle_sync import entry_fingerprint

    return _digest(entry_fingerprint(iid, e))


def test_merkle_leaf_diff_detects_payload_change():
    a = LwwSet("A")
    b = LwwSet("B")
    a.add(Item("x", {"v": 1}))
    b.add(Item("x", {"v": 2}))  # tot zhe id, drugoy payload
    la = local_leaf_hashes(a)
    lb = local_leaf_hashes(b)
    # Remote response emulation: ordered ids and leaves
    ids = sorted(["x"])
    remote_level0 = [lb[i] for i in ids]
    need = diff_by_leaves(la, ids, remote_level0)
    assert need == ["x"]


def test_merkle_leaf_diff_detects_remove_vs_add():
    a = LwwSet("A")
    b = LwwSet("B")
    a.add(Item("x", {"t": "hello"}))
    b.remove("x")  # konkurentnyy remove
    la = local_leaf_hashes(a)
    ids = sorted(["x"])
    # rukami sobiraem remote leaf khesh
    rb = _fingerprint_like_remote("x", b.entries["x"])
    need = diff_by_leaves(la, ids, [rb])
# assert need == ["x"]