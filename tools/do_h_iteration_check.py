# -*- coding: utf-8 -*-
"""
Self-check dlya Iteratsii H (CRDT + Merkle + CAS + P2P).
Zapusk:
  python -m tools.do_h_iteration_check
Vyvodit JSON s rezultatami i summarnym statusom.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict

from crdt.lww_set import LwwSet
from crdt.types import Item
from merkle.cas import CAS
from merkle.merkle_tree import Merkle
from routes.p2p_crdt_routes import CRDT
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def check_crdt() -> Dict[str, Any]:
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
    ok = (
        set(a.visible_items().keys())
        == {"x", "y", "z"}
        == set(b.visible_items().keys())
        == set(c.visible_items().keys())
    )
    return {"ok": ok, "visible": sorted(a.visible_items().keys())}


def check_cas() -> Dict[str, Any]:
    cas = CAS()
    blob = {"t": "hello", "n": 42}
    d1 = cas.put(blob)
    d2 = cas.put(blob)
    dedup = d1 == d2
    got = cas.get(d1)
    return {"ok": dedup and got is not None, "cid": d1, "len": len(got or b"")}


def check_merkle(n: int = 256) -> Dict[str, Any]:
    s = LwwSet("M")
    for i in range(n):
        s.add(Item(f"k{i}", {"v": i}))
    ids = sorted(s.entries.keys())
    leaves = [
        json.dumps(s.entries[i].item.payload, ensure_ascii=False).encode("utf-8") for i in ids
    ]
    t0 = time.perf_counter()
    root, levels = Merkle.build(leaves)
    t1 = time.perf_counter()
    return {
        "ok": len(levels) >= 1 and isinstance(root, str),
        "levels": len(levels),
        "ms": round((t1 - t0) * 1000, 2),
    }


def run_all() -> Dict[str, Any]:
    r1 = check_crdt()
    r2 = check_cas()
    r3 = check_merkle()
    overall = all([r1["ok"], r2["ok"], r3["ok"]])
    return {
        "ok": overall,
        "crdt": r1,
        "cas": r2,
        "merkle": r3,
        "peer": CRDT.peer_id,
        "clock": CRDT.clock,
    }

if __name__ == "__main__":
    result = run_all()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("ok") else 1)
