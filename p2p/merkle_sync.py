# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Dict, List, Tuple

from merkle.cas import _digest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def entry_fingerprint(item_id: str, e) -> bytes:
    """Exactly the same sheet as in rutes/p2p_tsrdt_rutes._entry_fingerprint."""
    payload_digest = _digest(
        json.dumps(e.item.payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    add_s = f"{e.add.peer}:{e.add.ts}" if e.add else "-"
    rem_s = f"{e.rem.peer}:{e.rem.ts}" if e.rem else "-"
    s = f"{item_id}|{add_s}|{rem_s}|{payload_digest}"
    return s.encode("utf-8")


def local_leaf_hashes(crdt) -> Dict[str, str]:
    """Vozvraschaet id -> leaf_hash (digest(fingerprint))."""
    ids = sorted(crdt.entries.keys())
    out: Dict[str, str] = {}
    for iid in ids:
        fp = entry_fingerprint(iid, crdt.entries[iid])
        out[iid] = _digest(fp)
    return out


def diff_by_leaves(
    local: Dict[str, str], remote_ids: List[str], remote_leaf_level: List[str]
) -> List[str]:
    """Compares local and remote leaves. Returns a list of ids where the hashes are different or there is no id locally."""
    need: List[str] = []
    for iid, rh in zip(remote_ids, remote_leaf_level):
        lh = local.get(iid)
        if lh != rh:
            need.append(iid)
    return need
