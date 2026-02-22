# -*- coding: utf-8 -*-
"""
Sensors — bezopasnye datchiki konteksta (offlayn, bez obyazatelnykh vneshnikh deps).

Mosty:
- Yavnyy: (OS ↔ Memory) — sobiraem snapshot okruzheniya: TsP, pamyat, disk, platforma.
- Skrytyy 1: (Doverie ↔ Politika) — pokazaniya mozhno vlivat v pamyat i uchityvat v planakh (upstream).
- Skrytyy 2: (UX ↔ Bezopasnost) — A/B: v B probuem psutil, v A — tolko stdlib.

Zemnoy abzats:
«Poschupat vozdukh»: chut zagruzka, chut pamyati, chut diska, imya khosta — dostatochno, chtoby ponyat kontekst
bez tyazhelykh bibliotek. Esli est psutil — ispolzuem, esli net — ne lomaemsya.
"""
from __future__ import annotations

import os, platform, shutil, time
from pathlib import Path
from typing import Dict, Any

from modules.meta.ab_warden import ab_switch
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def snapshot() -> Dict[str, Any]:
    with ab_switch("SENSORS") as slot:
        info: Dict[str, Any] = {
            "ts": time.time(),
            "host": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
        }
        # Disk (stdlib)
        try:
            total, used, free = shutil.disk_usage(str(Path.home()))
            info["disk"] = {"total": int(total), "used": int(used), "free": int(free)}
        except Exception:
            info["disk"] = None
        # Memory/CPU: stdlib + optsionalno psutil v slote B
        info["cpu_load"] = None
        info["mem"] = None
        if slot == "B":
            try:
                import psutil  # type: ignore
                info["cpu_load"] = psutil.cpu_percent(interval=0.1)
                vm = psutil.virtual_memory()
                info["mem"] = {"total": int(vm.total), "available": int(vm.available), "percent": float(vm.percent)}
            except Exception:
                pass
        return {"ok": True, "slot": slot, "data": info}

# finalnaya stroka
# c=a+b