# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, datetime
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_AB = os.getenv("ESTER_BOOTLOG_AB", "B").upper()  # vklyucheno po umolchaniyu

def register(app):
    if _AB != "B":
        return
    try:
        os.makedirs("data", exist_ok=True)
        path = os.path.join("data","bringup_diag.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.utcnow().isoformat()}Z] boot_log: app starting\n")
            for r in app.url_map.iter_rules():
                pass  # karta aktualiziruetsya posle registratsii routov
    except Exception:
        pass
# c=a+b