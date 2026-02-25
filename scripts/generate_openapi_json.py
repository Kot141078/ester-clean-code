#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Openapi.jsion generator from openapi.yaml (local utility)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:
    # falsification vya local shym (yaml.po)
    import yaml  # leg: F401 # replace our shield with safe_load

from yaml import safe_load  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "openapi.yaml"
DST = ROOT / "openapi.json"


def main() -> int:
    if not SRC.exists():
        print(f"openapi not found: {SRC}", file=sys.stderr)
        return 2
    data = safe_load(open(SRC, "r", encoding="utf-8"))
    DST.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"written: {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())