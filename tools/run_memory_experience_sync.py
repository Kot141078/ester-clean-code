# -*- coding: utf-8 -*-
"""tools/run_memory_experience_sync.py — ruchnoy zapusk sinkhronizatsii sloya opyta.

MOSTY:
- Yavnyy: (CLI ↔ modules.memory.experience) - edinaya tochka zapuska sync_experience().
- Skrytyy #1: (sys.path ↔ struktura repo) - fiksiruet problemu ModuleNotFoundError dlya modules.*.
- Skrytyy #2: (operator ↔ anchors) — pozvolyaet uvidet, kak insayty perekhodyat v opornye tochki.

ZEMNOY ABZATs:
Inzhenerno eto upravlyaemyy servisnyy vyzov: cron/Task Scheduler mozhet spokoyno dergat
etot skript, ne znaya vnutrenney struktury Python-paketov.
# c=a+b"""
from __future__ import annotations

import os
import sys
import json

# Add the project root (the folder where modules/ are located)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.memory import experience  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "manual"
    res = experience.sync_experience(mode=mode)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if bool(res.get("ok", True)) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))