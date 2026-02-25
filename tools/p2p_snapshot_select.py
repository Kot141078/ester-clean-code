# -*- coding: utf-8 -*-
"""Vyborochnyy eksport/import snapshota CRDT po prefiksu id (ili regex).
Primery:
  python -m tools.p2p_snapshot_select export out.json --prefix "doc:"
  python -m tools.p2p_snapshot_select import in.json"""
from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict, Optional

from routes.p2p_crdt_routes import CRDT  # lokalnyy globalnyy nabor
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _build_subset(prefix: Optional[str], regex: Optional[str]) -> Dict[str, Any]:
    filt = None
    if prefix:
        filt = lambda s: s.startswith(prefix)
    elif regex:
        rx = re.compile(regex)
        filt = lambda s: bool(rx.search(s))
    else:
        filt = lambda s: True

    subset = {}
    for iid, e in CRDT.entries.items():
        if not filt(iid):
            continue
        subset[iid] = {
            "item": {"id": e.item.id, "payload": e.item.payload},
            "add": ({"peer": e.add.peer, "ts": e.add.ts} if e.add else None),
            "rem": ({"peer": e.rem.peer, "ts": e.rem.ts} if e.rem else None),
        }
    return {
        "peer": CRDT.peer_id,
        "clock": CRDT.clock,
        "entries": subset,
    }


def do_export(path: str, prefix: Optional[str], regex: Optional[str]) -> None:
    snap = _build_subset(prefix, regex)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    print(f"Exported subset snapshot -> {path}")


def do_import(path: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    from crdt.lww_set import LwwSet

    other = LwwSet.from_snapshot(data)
    CRDT.merge(other)
    print("Imported subset snapshot OK")


def _usage():
    print(
        "Usage:\n  export <file.json> [--prefix STR | --regex REGEX]\n  import <file.json>",
        file=sys.stderr,
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        _usage()
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "export":
        path = sys.argv[2]
        prefix = None
        regex = None
        for i, a in enumerate(sys.argv[3:], start=3):
            if a == "--prefix" and i + 1 < len(sys.argv):
                prefix = sys.argv[i + 1]
            if a == "--regex" and i + 1 < len(sys.argv):
                regex = sys.argv[i + 1]
        do_export(path, prefix, regex)
    elif cmd == "import":
        do_import(sys.argv[2])
    else:
        _usage()
# sys.exit(1)