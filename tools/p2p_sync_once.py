# -*- coding: utf-8 -*-
"""One-time reconciliation/synchronization run (for crowns/manual call)."""
from __future__ import annotations

import json

from scheduler.sync_job import sync_once  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

if __name__ == "__main__":
    res = sync_once()
    print(json.dumps(res, ensure_ascii=False, indent=2))