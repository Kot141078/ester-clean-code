# -*- coding: utf-8 -*-
"""
modules/hw/monitor.py — minimalnyy monitor zheleza: CPU/RAM/disk/temperatury (esli dostupny).

Mosty:
- Yavnyy: (Zhelezo ↔ Nadezhnost) rannie priznaki peregreva/perepolneniya.
- Skrytyy #1: (Kibernetika ↔ Degradatsiya) mozhno podklyuchat k degradatsii v read-only.
- Skrytyy #2: (Nablyudaemost ↔ DR) signal do togo, kak «vzorvetsya».

Zemnoy abzats:
Smotrim «strelochki»: esli zharko/tesno — tormozim zaranee.

# c=a+b
"""
from __future__ import annotations
import shutil, os
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def status() -> Dict[str, Any]:
    total, used, free = shutil.disk_usage(".")
    rep = {"disk_free": free, "disk_total": total}
    # pamyat/CPU/temperatury — best-effort
    try:
        import psutil  # type: ignore
        rep["cpu_load"] = psutil.getloadavg() if hasattr(psutil, "getloadavg") else list(psutil.cpu_percent(percpu=True))
        vm = psutil.virtual_memory()
        rep["ram_used"] = vm.used; rep["ram_total"] = vm.total
        temps = getattr(psutil, "sensors_temperatures", lambda: {})()
        if temps: rep["temps"] = {k: [t.current for t in v] for k,v in temps.items()}
    except Exception:
        rep["cpu_load"] = []; rep["ram_used"]=rep["ram_total"]=0
    return {"ok": True, **rep}
# c=a+b