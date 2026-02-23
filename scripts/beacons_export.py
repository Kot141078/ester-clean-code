# scripts/beacons_export.py
# -*- coding: utf-8 -*-
"""
scripts/beacons_export.py — eksport mayakov aktivnosti v JSON.

Zapusk:
  python scripts/beacons_export.py
  # optsionalno:
  #   LIMIT=500
  #   SINCE=1737600000.0
  #   KINDS=backup.run,backup.done,scheduler:tick

Vyvod:
  Pechataet JSON s "items": [...], "count": N
"""
from __future__ import annotations

import json
import os
from typing import List, Optional

from modules.kg_beacons_query import list_beacons
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main() -> int:
    limit = int(os.getenv("LIMIT") or "200")
    since_env = os.getenv("SINCE")
    kinds_env = os.getenv("KINDS") or ""
    kinds: Optional[List[str]] = None
    if kinds_env.strip():
        kinds = [s.strip() for s in kinds_env.split(",") if s.strip()]
    since_ts = float(since_env) if since_env else None

    rows = list_beacons(limit=limit, since=since_ts, kinds=kinds)
    print(
        json.dumps(
            {"ok": True, "items": rows, "count": len(rows)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())