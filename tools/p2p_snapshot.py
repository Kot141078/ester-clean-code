# -*- coding: utf-8 -*-
"""
Eksport/import snapshota CRDT v/iz fayla s ispolzovaniem CAS.
"""
from __future__ import annotations

import json
import sys

from merkle.cas import CAS
from routes.p2p_crdt_routes import CRDT  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

USAGE = """Usage:
  python -m tools.p2p_snapshot export <file.json>
  python -m tools.p2p_snapshot import <file.json>
"""


def do_export(path: str):
    snap = CRDT.snapshot()
    cid = CAS().put(snap)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"cid": cid, "snapshot": snap}, f, ensure_ascii=False, indent=2)
    print(f"Exported snapshot -> {path} (cid={cid})")


def do_import(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    from crdt.lww_set import LwwSet

    other = LwwSet.from_snapshot(data.get("snapshot") or data)
    from routes.p2p_crdt_routes import CRDT as LOCAL

    LOCAL.merge(other)
    print("Imported snapshot OK")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in {"export", "import"}:
        print(USAGE)
        sys.exit(1)
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "export":
        do_export(path)
    else:
        do_import(path)
