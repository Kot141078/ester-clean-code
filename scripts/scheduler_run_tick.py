# scripts/scheduler_run_tick.py
# -*- coding: utf-8 -*-
"""
scripts/scheduler_run_tick.py — edinichnyy tik planirovschika.
Zapusk: python scripts/scheduler_run_tick.py
ENV:
  NOW_TS   — optsionalno, float-metka vremeni dlya prinuditelnogo «seychas»
"""
from __future__ import annotations

import json
import os

from modules import events_bus
from modules.scheduler_engine import run_due
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main() -> int:
    now_env = os.getenv("NOW_TS")
    now_ts = float(now_env) if now_env else None
    try:
        # mayak pered zapuskom (best-effort)
        try:
            events_bus.append("scheduler:runner_invoked", {"now_ts": now_ts})
        except Exception:
            pass

        report = run_due(now_ts=now_ts)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ok") else 1
    except Exception as e:
        err = {"ok": False, "error": str(e)}
        print(json.dumps(err, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())