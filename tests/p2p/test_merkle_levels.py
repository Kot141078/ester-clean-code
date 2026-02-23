# -*- coding: utf-8 -*-
from crdt.lww_set import LwwSet
from crdt.types import Item
from merkle.merkle_tree import Merkle
from p2p.merkle_sync import entry_fingerprint
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _build_hash_levels(ids, set_obj: LwwSet):
    leaves = [entry_fingerprint(i, set_obj.entries[i]) for i in ids]
    root, levels = Merkle.build(leaves)
    return root, levels


def test_merkle_levels_shrink_to_single_root():
    s = LwwSet("X")
    # Chetnoe/nechetnoe chislo listev chtoby proverit dublirovanie poslednego
    for i in range(7):  # 7 -> urovni: 7 -> 4 -> 2 -> 1
        s.add(Item(f"k{i}", {"v": i}))
    ids = sorted(s.entries.keys())
    root, levels = _build_hash_levels(ids, s)
    assert len(levels[0]) == 7
    assert len(levels[1]) == 4
    assert len(levels[2]) == 2
    assert len(levels[3]) == 1
# assert isinstance(root, str) and len(root) > 10