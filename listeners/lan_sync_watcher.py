# -*- coding: utf-8 -*-
"""listeners.lan_sync_watcher - nablyudenie za LAN-resursami i sovmestimyy API dlya routov.

MOSTY:
- Yavnyy: (REST ↔ Nablyudatel) start/stop/status/tick_once — upravlyayut oprosom i snimkami FS.
- Skrytyy #1: (Faylovaya sistema ↔ Obmen) scan/collect gotovyat sostoyanie dlya differentsiatsii.
- Skrytyy #2: (A/B-sloty ↔ Bezopasnost) bez fonovykh potokov: “B” rezhim — tolko hand tick.

ZEMNOY ABZATs:
This is “peydzher”: fiksiruet bazovuyu telemetriyu, delaet snimok kataloga i nichego ne shlet naruzhu.
Safely dazhe v zakrytoy seti: vse operatsii lokalnye, bez soketov/daunstrimov.
# c=a+b"""
from __future__ import annotations

import os
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = [
    "start", "stop", "status", "tick_once",
    "scan", "collect", "diff"
]

# ------------------------ Vnutrennee sostoyanie ------------------------

_STATE: Dict[str, Any] = {
    "running": False,
    "interval": 2,
    "ticks": 0,
    "started_ts": None,     # type: Optional[int]
    "stopped_ts": None,     # type: Optional[int]
    "last_error": None,     # type: Optional[str]
    "last_scan": None,      # type: Optional[Dict[str, Any]]
    "last_scan_ts": None,   # type: Optional[int]
    "peers": [],            # expandable in the future
    "ab": (os.getenv("ESTER_LAN_WATCH_AB") or "A").strip().upper(),
}

# ------------------------ Primitivnye operatsii ------------------------

def _listdir_safe(path: str) -> List[str]:
    try:
        return sorted(os.listdir(path))
    except Exception:
        return []

def scan(root: str = "data") -> Dict[str, Any]:
    """Returns a "snapshot" of a directory: a list of subdirectories and first-level files."""
    root = os.path.abspath(root)
    items = _listdir_safe(root)
    return {"ok": True, "root": root, "items": items}

def collect(root: str = "data") -> Dict[str, Any]:
    """Collects a simplified state dictionary for further differentiation."""
    shot = scan(root)
    return {"ok": True, "state": shot}

def diff(local: Dict[str, Any], remote: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sravnivaet dva snimka (po imenam elementov).
    """
    l = set((local or {}).get("items", []) or [])
    r = set((remote or {}).get("items", []) or [])
    return {"ok": True, "add": sorted(list(r - l)), "del": sorted(list(l - r))}

# ------------------------ Sovmestimyy publichnyy API ------------------------

def start(interval: int = 2, root: str = "data") -> Dict[str, Any]:
    """Compatible launch point: includes "observer" (no background threads).
    Returns the status after setting the interval."""
    try:
        _STATE["interval"] = int(interval or 2)
    except Exception:
        _STATE["interval"] = 2
    _STATE["running"] = True
    _STATE["ticks"] = 0
    _STATE["started_ts"] = int(time.time())
    _STATE["stopped_ts"] = None
    _STATE["last_error"] = None
    # pervyy snimok — srazu
    try:
        _STATE["last_scan"] = scan(root)
        _STATE["last_scan_ts"] = int(time.time())
    except Exception as e:
        _STATE["last_error"] = f"{type(e).__name__}: {e}"
    return status()

def stop(reason: str | None = None) -> Dict[str, Any]:
    _STATE["running"] = False
    _STATE["stopped_ts"] = int(time.time())
    return status()

def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "running": bool(_STATE["running"]),
        "interval": int(_STATE["interval"]),
        "ticks": int(_STATE["ticks"]),
        "ab": _STATE["ab"],
        "started_ts": _STATE["started_ts"],
        "stopped_ts": _STATE["stopped_ts"],
        "last_scan": _STATE["last_scan"],
        "last_scan_ts": _STATE["last_scan_ts"],
        "last_error": _STATE["last_error"],
        "peers": list(_STATE.get("peers") or []),
    }

def tick_once(root: str = "data") -> Dict[str, Any]:
    """One-time loop: takes a snapshot of the directory and increments the tick counter.
    Used by the router for manual “heartbeat” without background flow."""
    try:
        _STATE["last_scan"] = scan(root)
        _STATE["last_scan_ts"] = int(time.time())
        _STATE["ticks"] = int(_STATE["ticks"]) + 1
        _STATE["last_error"] = None
    except Exception as e:
        _STATE["last_error"] = f"{type(e).__name__}: {e}"
    return status()