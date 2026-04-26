# scripts/beacons_export.py
# -*- coding: utf-8 -*-
"""
scripts/beacons_export.py — экспорт маяков активности в JSON.

Запуск:
  python scripts/beacons_export.py
  # опционально:
  #   LIMIT=500
  #   SINCE=1737600000.0
  #   KINDS=backup.run,backup.done,scheduler:tick

Вывод:
  Печатает JSON с "items": [...], "count": N
"""
from __future__ import annotations

import json
import os
from typing import List, Optional

from modules.kg_beacons_query import list_beacons


def main() -> int:
    try:
        limit = int(os.getenv("LIMIT") or "200")
    except Exception:
        limit = 200
    since_env = os.getenv("SINCE")
    kinds_env = os.getenv("KINDS") or ""
    kinds: Optional[List[str]] = None
    if kinds_env.strip():
        kinds = [s.strip() for s in kinds_env.split(",") if s.strip()]
    try:
        since_ts = float(since_env) if since_env else None
    except Exception:
        since_ts = None

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
