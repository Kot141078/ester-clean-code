# -*- coding: utf-8 -*-
"""
scheduler/cron_memory_maintenance.py — «ruchka pod cron» dlya tekhprotsedur pamyati.

API (vnutr.):
  • run_pipeline(tasks:list[str]) -> dict   # tasks ⊆ {"heal","compact","snapshot","reindex"}

Realizatsiya:
  • Pytaetsya vyzvat suschestvuyuschie HTTP/lokalnye protsedury; pri otsutstv. — bezoshibochnyy NOOP.
  • Otchet i metriki otdayutsya cherez /admin/mem/cron/run i /metrics/mem_maintenance.

Mosty:
- Yavnyy: (Memory ↔ Ekspluatatsiya) formalizuet nochnye protsedury bez skrytykh demonov.
- Skrytyy #1: (Inzheneriya ↔ Nadezhnost) soft-fail — dazhe esli kakoy-to shag nedostupen.
- Skrytyy #2: (Kibernetika ↔ Kontrol) integriruetsya v RuleHub/raspisanie.

Zemnoy abzats:
Eto knopka «nochnaya uborka»: proshlis pylesosom po pamyati — stala kompaktnee i chische.

# c=a+b
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_CNT = {"runs_total": 0, "steps_ok": 0, "steps_fail": 0}

def _try_http(path: str, payload: Dict[str, Any] | None = None, timeout: float = 5.0) -> bool:
    try:
        import requests  # noqa
        base = os.getenv("ESTER_BASE_URL", "http://127.0.0.1:8000")
        if payload is None:
            r = requests.post(base + path, timeout=timeout)
        else:
            r = requests.post(base + path, json=payload, timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False

def run_pipeline(tasks: List[str]) -> Dict[str, Any]:
    _CNT["runs_total"] += 1
    report = []
    for t in tasks:
        ok = False
        if t == "heal":
            ok = _try_http("/mem/heal") or _try_http("/mem/repair")
        elif t == "compact":
            ok = _try_http("/mem/compact")
        elif t == "snapshot":
            ok = _try_http("/mem/snapshot")
        elif t == "reindex":
            ok = _try_http("/mem/reindex") or _try_http("/search/reindex")
        else:
            ok = True  # neizvestnaya zadacha — ignor
        report.append({"task": t, "ok": bool(ok)})
        _CNT["steps_ok" if ok else "steps_fail"] += 1
    return {"ok": True, "report": report, "ts": int(time.time())}

def counters() -> Dict[str, int]:
    return dict(_CNT)
