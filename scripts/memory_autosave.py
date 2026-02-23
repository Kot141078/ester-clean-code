# -*- coding: utf-8 -*-
"""
scripts/memory_autosave.py — otdelnyy zapusk avtosokhraneniya.

Mozhet ispolzovatsya v systemd ili planirovschike zadach:
  python scripts/memory_autosave.py  (sokhranyaet kazhdye 60s)

# c=a+b
"""
import time
from modules.memory import store
from modules.memory.boot import preload_memory, graceful_shutdown
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

preload_memory()
try:
    while True:
        time.sleep(60)
        store.snapshot()
        print("[Memory] Periodic save done.")
except KeyboardInterrupt:
    graceful_shutdown()