# scripts/proactive_consume_once.py
# -*- coding: utf-8 -*-
"""
scripts/proactive_consume_once.py — odnorazovaya obrabotka sobytiy Proactive 2.0.

Ispolzovanie (dlya cron/systemd ili ruchnogo zapuska):
  python scripts/proactive_consume_once.py
  # optsionalno peremennye okruzheniya:
  #   LIMIT=500

Povedenie:
  - beret sokhranennyy offset <PERSIST_DIR>/proactive/offset.json
  - obrabatyvaet sobytiya (automation:run_due, dream:tick, ingest:queue_reingest i dr.)
  - sokhranyaet novyy offset, pechataet JSON-otchet
"""
from __future__ import annotations

import json
import os

from modules.proactive_engine import consume_once
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main() -> int:
    limit = int(os.getenv("LIMIT") or "200")
    report = consume_once(limit=limit)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())