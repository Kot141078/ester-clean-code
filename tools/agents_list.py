# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.agents import runtime as agents_runtime


def main() -> int:
    rep = agents_runtime.list_agents()
    print(json.dumps(rep, ensure_ascii=True, indent=2))
    return 0 if bool(rep.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
