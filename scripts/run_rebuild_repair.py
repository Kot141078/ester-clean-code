# -*- coding: utf-8 -*-
"""scripts/run_rebuild_repair.py - CLI dlya skvoznogo Rebuild/Repair (Structured + Vector + KG).

Primery:
  python -m scripts.run_rebuild_repair --json"""

from __future__ import annotations

import json

from modules.rebuild_repair import RebuildRepairEngine  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main(argv=None) -> int:
    eng = RebuildRepairEngine()
    rep = eng.run_full()
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())