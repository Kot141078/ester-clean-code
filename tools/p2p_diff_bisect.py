# -*- coding: utf-8 -*-
"""CLI: bystryy dvoichnyy poisk raskhozhdeniy po merklu s udalennym uzlom.
Rabotaet paketno, skachivaya kheshi urovnya 0 (listya) chastyami.
Primer:
  python -m tools.p2p_diff_bisect http://10.0.0.12:5000 [chunk=2048]
Vyvodit JSON so spiskom nesovpadayuschikh id."""
from __future__ import annotations

import json
import sys
from typing import List

from p2p.merkle_sync import diff_by_leaves, local_leaf_hashes
from p2p.sync_client import state_level
from routes.p2p_crdt_routes import CRDT  # lokalnyy CRDT
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def run(base_url: str, chunk: int = 2048) -> dict:
    # we get general statistics
    st0 = state_level(base_url, level=0, offset=0, limit=1)
    if not st0.get("ok"):
        return {"ok": False, "err": st0.get("error") or st0.get("status")}
    total = int(st0.get("total_hashes") or 0)
    local_map = local_leaf_hashes(CRDT)

    diff_ids: List[str] = []
    off = 0
    while off < total:
        st = state_level(base_url, level=0, offset=off, limit=chunk)
        if not st.get("ok"):
            return {"ok": False, "err": st.get("error") or st.get("status")}
        ids = list(st.get("leaf_ids") or [])
        hashes = list(st.get("hashes") or st.get("level") or [])
        need = diff_by_leaves(local_map, ids, hashes)
        diff_ids.extend(need)
        off += len(ids) if ids else chunk
        if not ids:
            break
    return {
        "ok": True,
        "peer": base_url,
        "total_remote_leaves": total,
        "local_leaves": len(local_map),
        "diff_ids_count": len(diff_ids),
        "diff_ids": diff_ids[:1000],  # safety cap
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m tools.p2p_diff_bisect <base_url> [chunk]", file=sys.stderr)
        sys.exit(1)
    base = sys.argv[1]
    chunk = int(sys.argv[2]) if len(sys.argv) > 2 else 2048
    res = run(base, chunk)
    print(json.dumps(res, ensure_ascii=False, indent=2))
# sys.exit(0 if res.get("ok") else 2)