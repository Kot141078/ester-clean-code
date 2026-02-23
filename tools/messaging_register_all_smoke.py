# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Set

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _import_optional(name: str):
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def _bp_names(app: Flask) -> Set[str]:
    return set(getattr(app, "blueprints", {}).keys())


def main() -> int:
    out: Dict[str, Any] = {"ok": False}
    app = Flask("messaging_register_all_smoke")

    try:
        telegram_routes = importlib.import_module("routes.telegram_routes")
        messaging_register_all = importlib.import_module("routes.messaging_register_all")

        # Simulate pre-registration by canonical routes before messaging_register_all.
        telegram_routes.register(app)
        tg_send = _import_optional("routes.telegram_send_routes")
        if tg_send is not None and callable(getattr(tg_send, "register", None)):
            tg_send.register(app)

        bp_before = _bp_names(app)
        messaging_register_all.register(app)
        bp_after_first = _bp_names(app)
        messaging_register_all.register(app)
        bp_after_second = _bp_names(app)

        telegram_bp_name = str(getattr(getattr(telegram_routes, "bp", None), "name", "") or "")
        if not telegram_bp_name:
            telegram_bp_name = str(getattr(getattr(telegram_routes, "telegram_bp", None), "name", "") or "")

        ok = (
            bool(telegram_bp_name)
            and (telegram_bp_name in bp_after_first)
            and (telegram_bp_name in bp_after_second)
            and (bp_after_second == bp_after_first)
            and (len(bp_after_second) >= len(bp_before))
        )

        out = {
            "ok": ok,
            "telegram_bp": telegram_bp_name,
            "blueprints_before": sorted(bp_before),
            "blueprints_after_first": sorted(bp_after_first),
            "blueprints_after_second": sorted(bp_after_second),
            "blueprints_count": len(bp_after_second),
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    except Exception as e:
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

