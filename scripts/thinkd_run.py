# -*- coding: utf-8 -*-
"""
scripts/thinkd_run.py — bezopasnyy zapusk fonovogo myslitelya Ester.

Mosty:
- Yavnyy: (CLI ↔ modules.always_thinker) — pryamoy vkhod k fonovomu myshleniyu.
- Skrytyy #1: (PowerShell ↔ sys.path) — sam nakhodit koren proekta i dobavlyaet ego.
- Skrytyy #2: (Inzhener ↔ Volya) — yavnyy start avtonomnogo myshleniya po komande cheloveka.

Zemnoy abzats:
    # iz kornya proekta
    python scripts/thinkd_run.py
Skript zapuskaet always_thinker.start_background() s intervalom THINK_HEARTBEAT_SEC
i derzhit protsess do Ctrl+C.
# c=a+b
"""
from __future__ import annotations

import os
import sys
import time

# Obespechivaem, chto koren proekta (papka s modules/) v sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules import always_thinker  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main() -> None:
    interval = float(os.environ.get("THINK_HEARTBEAT_SEC", "30"))
    res = always_thinker.start_background(interval_sec=interval)
    print(f"[thinkd_run] background thinker started (interval={interval}s): {res}")
    try:
        while True:
            time.sleep(60.0)
    except KeyboardInterrupt:
        stop = always_thinker.stop_background()
        print(f"[thinkd_run] stopped: {stop}")


if __name__ == "__main__":
    main()