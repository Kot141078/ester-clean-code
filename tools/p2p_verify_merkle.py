# -*- coding: utf-8 -*-
"""SLI: Compare local merkle leaves with remote node and output id divergences.
Example:
  pothon -m tools.p2p_verify_merkle http://10.0.0.11:5000"""
from __future__ import annotations

import json
import sys
from typing import List

from p2p.merkle_sync import diff_by_leaves, local_leaf_hashes
from p2p.sync_client import state_level
from routes.p2p_crdt_routes import CRDT  # lokalnyy CRDT
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def verify(base_url: str) -> dict:
    st = state_level(base_url, level=0)
    if not st.get("ok"):
        return {"ok": False, "err": st.get("error") or st.get("status")}
    remote_ids: List[str] = list(st.get("leaf_ids") or [])
    remote_leaf_level: List[str] = list(st.get("level") or [])
    local_map = local_leaf_hashes(CRDT)
    need = diff_by_leaves(local_map, remote_ids, remote_leaf_level)
    return {
        "ok": True,
        "remote": base_url,
        "remote_root": st.get("merkle_root") or st.get("root"),
        "count_remote": len(remote_ids),
        "count_local": len(local_map),
        "diff_ids_count": len(need),
        "diff_ids_sample": need[:50],
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m tools.p2p_verify_merkle <base_url>", file=sys.stderr)
        sys.exit(1)
    res = verify(sys.argv[1])
    print(json.dumps(res, ensure_ascii=False, indent=2))
# sys.exit(0 if res.get("ok") else 2)