# -*- coding: utf-8 -*-
"""bin/rpa_schedule_tick.py - odnokratnyy tik planirovschika (CLI).
Zapuskat raz v minutu/5 minut planirovschikom OS.

Primer:
  python bin/rpa_schedule_tick.py
  (ili) powershell -File scripts/desktop/windows/schedule_tick_task.ps1

Vozvratit JSON s rezultatami zapuskov.

# c=a+b"""
from __future__ import annotations
import json
from modules.thinking.rpa_workflows import sched_tick
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

if __name__ == "__main__":
    res = sched_tick(None)
    print(json.dumps(res, ensure_ascii=False))