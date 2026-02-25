# -*- coding: utf-8 -*-
"""tools/register_memory_sleep_alias.py

Utilita dlya bezopasnogo dobavleniya routes.memory_sleep_routes_alias
v data/app/extra_routes.json.

MOSTY:
  • Yavnyy: CLI ↔ extra_routes.json ↔ Flask boot.
  • Skrytyy #1: Dev-sborka ↔ prodovyy konfig (odin istochnik pravdy).
  • Skrytyy #2: Chelovek-operator ↔ avtomaticheskaya pamyat sna.

ZEMNOY ABZATs:
Po suti - eto "vstavit novyy avtomat v shinoprovod": addavlyaem modul routetov
v spisok avtozagruzki, ne lomaya suschestvuyuschie stroki i ne trogaya app.py vruchnuyu."""
from __future__ import annotations

import json
import os
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "app"
DATA.mkdir(parents=True, exist_ok=True)
PATH = DATA / "extra_routes.json"

TARGET = "routes.memory_sleep_routes_alias"


def main() -> int:
    cur = []

    if PATH.exists():
        try:
            cur = json.loads(PATH.read_text(encoding="utf-8"))
            if not isinstance(cur, list):
                raise TypeError("extra_routes.json must be a JSON list")
        except Exception as e:
            print(f"[err] extra_routes.json parse failed: {e}")
            return 2

    if TARGET in cur:
        print(f"[ok] {TARGET} already present in {PATH.as_posix()}")
        return 0

    cur.append(TARGET)
    PATH.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] added {TARGET} to {PATH.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())