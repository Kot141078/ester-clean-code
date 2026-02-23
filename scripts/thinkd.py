# -*- coding: utf-8 -*-
"""
Nezavisimyy demon dlya lokalnoy otladki «myslit vsegda».
Podnimaet tolko vorker (bez Flask). Ostanovit CTRL+C.

Ispolzovanie:
  THINK_HEARTBEAT_SEC=120 python scripts/thinkd.py
"""
from modules.always_thinker import start_background, stop_background
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

if __name__ == "__main__":
    start_background()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_background()