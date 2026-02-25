# -*- coding: utf-8 -*-
"""Benchmark: postroenie Merkle i vychislenie listev dlya 10k klyuchey.
Tsel DoD: lokalno ~<200ms/uzel (depending on CPU; orientir).
Zapusk:
  python -m tools.bench_merkle [N=10000]"""
from __future__ import annotations

import json
import os
import random
import time
from typing import List

from crdt.lww_set import LwwSet
from crdt.types import Item
from merkle.cas import _digest
from merkle.merkle_tree import Merkle
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _entry_fingerprint(iid: str, payload: dict) -> bytes:
    pd = _digest(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    s = f"{iid}|{pd}"
    return s.encode("utf-8")


def run(n: int = 10000) -> dict:
    s = LwwSet("bench")
    for i in range(n):
        s.add(Item(f"k{i}", {"v": i}))
    ids = sorted(s.entries.keys())
    leaves: List[bytes] = []
    t0 = time.perf_counter()
    for iid in ids:
        leaves.append(_entry_fingerprint(iid, s.entries[iid].item.payload))
    t1 = time.perf_counter()
    root, levels = Merkle.build(leaves)
    t2 = time.perf_counter()

    return {
        "n": n,
        "leaf_hash_time_ms": round((t1 - t0) * 1000, 2),
        "merkle_build_time_ms": round((t2 - t1) * 1000, 2),
        "total_time_ms": round((t2 - t0) * 1000, 2),
        "levels": len(levels),
        "root": root[:16] + "...",
    }


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv("N", "10000"))
    res = run(n)
# print(json.dumps(res, ensure_ascii=False, indent=2))