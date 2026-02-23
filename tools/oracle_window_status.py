# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import oracle_window


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def main() -> int:
    cur = oracle_window.current_window()
    out = {
        "ok": bool(cur.get("ok")),
        "enabled": _truthy(os.getenv("ESTER_ORACLE_ENABLE", "0")),
        "open": bool(cur.get("open")),
        "window_id": cur.get("window_id"),
        "remaining_sec": int(cur.get("remaining_sec") or 0),
        "budgets": dict(cur.get("budgets") or {}),
        "budgets_left": dict(cur.get("budgets_left") or {}),
        "last_call": oracle_window.last_call_status(),
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if bool(out["ok"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
