# -*- coding: utf-8 -*-
"""
scripts/run_proactive.py — odnorazovyy ili periodicheskiy zapusk proaktivnykh pravil.
ENV:
  PROACTIVE_RULES=config/proactive_rules.yaml
  PROACTIVE_INTERVAL_SECS=0   # esli >0 — tsikl s pauzoy
  PROACTIVE_ONCE=1            # "1" => odin progon
"""
from __future__ import annotations

import json
import os
import time

from modules.thinking_pipelines import run_from_file  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _tick(path: str):
    rep = run_from_file(path)
    print(json.dumps({"ts": int(time.time()), "report": rep}, ensure_ascii=False))


def main():
    path = os.getenv("PROACTIVE_RULES", "config/proactive_rules.yaml")
    once = os.getenv("PROACTIVE_ONCE", "1").strip() == "1"
    interval = max(30, int(os.getenv("PROACTIVE_INTERVAL_SECS", "0") or "0")) if not once else 0
    if once or interval == 0:
        _tick(path)
        return
    try:
        while True:
            _tick(path)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()