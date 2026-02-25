# -*- coding: utf-8 -*-
"""modules.quality.guard - ingest, enable/disable i periodicheskaya proverka SLA.

Mosty:
- Yavnyy: REST-routy (/quality/*) ↔ etot modul (enable/disable/status/ingest/periodic_check).
- Skrytyy #1: (Telemetriya ↔ Alerting) — periodic_check() formiruet prostye HUD-opovescheniya bez vneshnikh zavisimostey.
- Skrytyy #2: (Okno nablyudeniya ↔ Svodka) — skolzyaschee okno po vremeni daet p90 i error_rate dlya dashborda/logov.

Zemnoy abzats:
Eto “semafor u stanka”: my skladyvaem sobytiya v korotkuyu operativnuyu ochered (pamyat protsessa),
a periodic_check() sravnivaet p90 i dolyu oshibok s porogami, chtoby ne dopustit degradatsii.
Nikakikh setevykh I/O - bezopasno dlya “zakrytoy korobki”.

# c=a+b"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = [
    "ingest", "enable", "disable", "status", "periodic_check"
]

# ----------------------- sostoyanie i konfig -----------------------

_ENABLED: bool = False

_CFG: Dict[str, Any] = {
    "window_sec": 300,      # sliding statistics window width (sec)
    "p90_ms": 800.0,        # target p90 by operation time (ms)
    "error_rate": 0.20,     # proportion of errors in the window (0..1)
    "hud_alerts": False,    # whether to include short HUD notifications in the response
}

# queue of events (in-memories), each element: ЗЗФ0З
_EVTS: List[Dict[str, Any]] = []

# latest summary (for status)
_LAST: Dict[str, Any] = {}

# A/B slot, without influence on contracts: in mode “B” only calculation, without HUD
_AB = (os.getenv("ESTER_QUALITY_GUARD_AB") or "A").strip().upper()


def _now() -> float:
    return time.time()


def _prune(now: Optional[float] = None) -> None:
    """Delete events outside the monitoring window."""
    now = now or _now()
    cutoff = now - float(_CFG.get("window_sec", 300))
    if not _EVTS:
        return
    # quick filtering by list
    keep = [e for e in _EVTS if float(e.get("ts", 0)) >= cutoff]
    if len(keep) != len(_EVTS):
        _EVTS[:] = keep


def _calc_stats() -> Tuple[int, float, float]:
    """Returns (count, p90_ms, error_rate) from events in the current window.
    Empty window => (0, 0.0, 0.0)"""
    n = len(_EVTS)
    if n == 0:
        return 0, 0.0, 0.0
    # p90
    vals = sorted(float(e.get("t_ms") or 0.0) for e in _EVTS)
    # indeks p90: ceil(0.9*n)-1 pri n>0
    import math
    idx = max(0, min(n - 1, int(math.ceil(0.9 * n) - 1)))
    p90 = float(vals[idx])
    # error rate
    err = sum(1 for e in _EVTS if not bool(e.get("ok", True)))
    erate = (err / n) if n else 0.0
    return n, p90, erate


# ----------------------- publichnyy API -----------------------

def ingest(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Receive one telemetry event.
    Expected fields (soft): ok:pain, t_ms:float, op:str"""
    ts = _now()
    evt = {
        "ts": ts,
        "ok": bool(payload.get("ok", True)),
        "t_ms": float(payload.get("t_ms", 0.0) or 0.0),
        "op": str(payload.get("op") or "op"),
    }
    _EVTS.append(evt)
    _prune(ts)
    return {"ok": True, "queued": len(_EVTS)}


def enable(config_or_flag: Any = True) -> Dict[str, Any]:
    """Enable quality control.
    Compatible with root: accepts either pain or JSION-config:
      ZZF0Z"""
    global _ENABLED
    # podderzhka bool
    if isinstance(config_or_flag, bool):
        _ENABLED = bool(config_or_flag)
        return status()

    # dictionary-config support
    cfg = dict(config_or_flag or {})
    _ENABLED = bool(cfg.get("enabled", True))
    for k in ("window_sec", "p90_ms", "error_rate", "hud_alerts"):
        if k in cfg:
            if k == "hud_alerts":
                _CFG[k] = bool(cfg[k])
            elif k in ("window_sec",):
                _CFG[k] = int(cfg[k])
            else:
                _CFG[k] = float(cfg[k])
    # ochistim okno pod novyy konfig
    _prune()
    return status()


def disable() -> Dict[str, Any]:
    return enable(False)


def status() -> Dict[str, Any]:
    # we give an easy summary without recalculation (so as not to touch the window)
    return {
        "ok": True,
        "enabled": _ENABLED,
        "cfg": dict(_CFG),
        "queue": len(_EVTS),
        "last": dict(_LAST),
        "ab": _AB,
    }


def periodic_check() -> Dict[str, Any]:
    """Periodicheskaya proverka SLA po skolzyaschemu oknu.
    Vozvraschaet: {
      ok, enabled, window_sec, count, p90_ms, error_rate,
      breached: {p90_ms:bool, error_rate:bool},
      alerts?: [stroki] # esli hud_alerts vklyuchen i est narusheniya
    }"""
    _prune()
    cnt, p90, erate = _calc_stats()
    thr_p90 = float(_CFG["p90_ms"])
    thr_er  = float(_CFG["error_rate"])
    breach_p = p90 > thr_p90 and cnt > 0
    breach_e = erate > thr_er and cnt > 0

    rep: Dict[str, Any] = {
        "ok": True,
        "enabled": _ENABLED,
        "window_sec": int(_CFG["window_sec"]),
        "count": cnt,
        "p90_ms": round(p90, 3),
        "error_rate": round(erate, 4),
        "breached": {"p90_ms": breach_p, "error_rate": breach_e},
    }

    # easy MOVE only if enabled and there are violations (and the slot does not prohibit)
    if _CFG.get("hud_alerts") and _AB != "B" and (breach_p or breach_e):
        alerts: List[str] = []
        if breach_p:
            alerts.append(f"Latency p90 {p90:.0f}ms > {thr_p90:.0f}ms")
        if breach_e:
            alerts.append(f"Errors {erate:.1%} > {thr_er:.1%}")
        rep["alerts"] = alerts

    # save for status()
    _LAST.clear()
    _LAST.update(rep)
    return rep