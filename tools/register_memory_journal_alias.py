# -*- coding: utf-8 -*-
"""tools/register_memory_journal_alias.py - registratsiya alias-routov zhurnala pamyati.

Add `routes.memory_journal_routes_alias` v data/app/extra_routes.json,
ne trogaya suschestvuyuschie route.

ZEMNOY ABZATs:
  Eto kak prolozhit dopolnitelnyy kabel v schitok, ne perekladyvaya vsyu provodku.
  Bezopasnyy sposob vklyuchit novyy kontur pamyati Ester.

# c=a+b"""
from __future__ import annotations

import json
import os
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROUTE = "routes.memory_journal_routes_alias"


def main() -> int:
    root = Path(os.getcwd())
    data_dir = root / "data" / "app"
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = data_dir / "extra_routes.json"

    if cfg_path.exists():
        try:
            routes = json.loads(cfg_path.read_text(encoding="utf-8"))
            if not isinstance(routes, list):
                routes = []
        except Exception:
            routes = []
    else:
        routes = []

    if ROUTE not in routes:
        routes.append(ROUTE)
        cfg_path.write_text(
            json.dumps(routes, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[ok] added {ROUTE} to {cfg_path}")
    else:
        print(f"[ok] {ROUTE} already present in {cfg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())