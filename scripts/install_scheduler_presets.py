# scripts/install_scheduler_presets.py
# -*- coding: utf-8 -*-
"""
scripts/install_scheduler_presets.py — ustanovka presetov planirovschika.

Zapusk:
  python scripts/install_scheduler_presets.py

Rezultat:
  - sozdaet zadachi dlya «dream ticks», «ezhednevnogo obzora» i «re-ingest ocheredey»
  - publikuet sobytie scheduler:presets_installed
"""
from __future__ import annotations

import json

from modules.scheduler_presets import install_scheduler_presets
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main() -> int:
    res = install_scheduler_presets()
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())