# -*- coding: utf-8 -*-
"""modules.selfmanage.host_probe — proverka vozmozhnostey khosta.

MOSTY:
- Yavnyy: (routes.selfmanage_routes ↔ Khost) probe_capabilities()/probe_host().
- Skrytyy #1: (Sistema ↔ Diagnostika) CPU/RAM/FS info pri nalichii psutil.
- Skrytyy #2: (Nadezhnost ↔ Fallback) rabotaet i bez psutil.

ZEMNOY ABZATs:
Bystraya spravka “na chem stoim”, bez privyazki k OS i vneshnim zavisimostyam.

# c=a+b"""
from __future__ import annotations
import os, platform
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def probe_capabilities() -> dict:
    info = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "cpus": os.cpu_count() or 1,
        "mem_bytes": None,
        "disk_free_bytes": None,
    }
    try:
        import psutil  # type: ignore
        info["mem_bytes"] = psutil.virtual_memory().total
        info["disk_free_bytes"] = psutil.disk_usage(".").free
    except Exception:
        pass
    return {"ok": True, "host": info}

# Alias ​​under the expected name from the routes
probe_host = probe_capabilities