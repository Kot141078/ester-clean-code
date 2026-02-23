# -*- coding: utf-8 -*-
"""
modules.scheduler_engine — minimalnyy offlayn-planirovschik.

MOSTY:
- Yavnyy: funktsii start()/stop()/status()/schedule()/cancel() ozhidayutsya routami.
- Skrytyy #1: (A/B-sloty) ESTER_AB_SCHEDULER vliyaet na «maneru» otveta (telemetriya).
- Skrytyy #2: (Idempotentnost) vse operatsii — in-proc bez pobochnykh effektov.

ZEMNOY ABZATs:
Eto «raspisalka na stole»: mozhno polozhit zadanie, posmotret spisok i otmenit — bez vneshnikh servisov.

# c=a+b
"""
from __future__ import annotations
import os
import time
import uuid
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_MODE = (os.getenv("ESTER_AB_SCHEDULER") or "A").upper()
_STATE: Dict[str, Any] = {
    "running": False,
    "started_at": None,  # type: Optional[float]
    "jobs": {},          # type: Dict[str, Dict[str, Any]]
    "started": 0,
    "stopped": 0,
}

def _now() -> float:
    return time.time()

def start() -> Dict[str, Any]:
    _STATE["running"] = True
    _STATE["started"] += 1
    _STATE["started_at"] = _STATE["started_at"] or _now()
    return {"ok": True, "mode": _MODE, "running": True, "started_at": _STATE["started_at"], "started": _STATE["started"]}

def stop() -> Dict[str, Any]:
    _STATE["running"] = False
    _STATE["stopped"] += 1
    return {"ok": True, "mode": _MODE, "running": False, "stopped": _STATE["stopped"], "stopped_at": _now()}

def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": _MODE,
        "running": bool(_STATE["running"]),
        "started_at": _STATE["started_at"],
        "jobs_total": len(_STATE["jobs"]),
        "ts": _now(),
    }

def schedule(spec: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Dobavit zadanie v raspisanie (minimum poley).
    spec: proizvolnyy slovar; id generiruetsya, next_run — seychas.
    """
    spec = dict(spec or {})
    job_id = spec.get("id") or str(uuid.uuid4())
    job = {
        "id": job_id,
        "spec": spec,
        "next_run": _now(),
        "active": True,
    }
    _STATE["jobs"][job_id] = job
    return {"ok": True, "job": job, "jobs_total": len(_STATE["jobs"])}

def cancel(job_id: str | None = None) -> Dict[str, Any]:
    """
    Otmenit zadanie po id. Esli id ne peredan — no-op (ok dlya API-kontrakta).
    """
    if not job_id:
        return {"ok": True, "canceled": 0, "reason": "empty_id"}
    removed = 1 if _STATE["jobs"].pop(job_id, None) is not None else 0
    return {"ok": True, "canceled": removed, "job_id": job_id, "jobs_total": len(_STATE["jobs"])}

# Utilita dlya polucheniya spiska — mozhet ozhidatsya sosednimi vyzovami
def list_jobs() -> List[Dict[str, Any]]:
    return list(_STATE["jobs"].values())

__all__ = ["start", "stop", "status", "schedule", "cancel", "list_jobs"]
# c=a+b