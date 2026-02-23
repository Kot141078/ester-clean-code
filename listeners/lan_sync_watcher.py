# -*- coding: utf-8 -*-
"""
listeners.lan_sync_watcher — nablyudenie za LAN-resursami i sovmestimyy API dlya routov.

MOSTY:
- Yavnyy: (REST ↔ Nablyudatel) start/stop/status/tick_once — upravlyayut oprosom i snimkami FS.
- Skrytyy #1: (Faylovaya sistema ↔ Obmen) scan/collect gotovyat sostoyanie dlya differentsiatsii.
- Skrytyy #2: (A/B-sloty ↔ Bezopasnost) bez fonovykh potokov: «B» rezhim — tolko ruchnoy tick.

ZEMNOY ABZATs:
Eto «peydzher»: fiksiruet bazovuyu telemetriyu, delaet snimok kataloga i nichego ne shlet naruzhu.
Bezopasno dazhe v zakrytoy seti: vse operatsii lokalnye, bez soketov/daunstrimov.
# c=a+b
"""
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
    "peers": [],            # rasshiryaemo v buduschem
    "ab": (os.getenv("ESTER_LAN_WATCH_AB") or "A").strip().upper(),
}

# ------------------------ Primitivnye operatsii ------------------------

def _listdir_safe(path: str) -> List[str]:
    try:
        return sorted(os.listdir(path))
    except Exception:
        return []

def scan(root: str = "data") -> Dict[str, Any]:
    """
    Vozvraschaet «snimok» kataloga: spisok podkatalogov i faylov pervogo urovnya.
    """
    root = os.path.abspath(root)
    items = _listdir_safe(root)
    return {"ok": True, "root": root, "items": items}

def collect(root: str = "data") -> Dict[str, Any]:
    """
    Sobiraet uproschennyy slovar sostoyaniya dlya dalneyshey differentsiatsii.
    """
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
    """
    Sovmestimaya tochka zapuska: vklyuchaet «nablyudatelya» (bez fonovykh potokov).
    Vozvraschaet status posle ustanovki intervala.
    """
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
    """
    Razovyy tsikl: delaet snimok kataloga i uvelichivaet schetchik tikov.
    Ispolzuetsya routerom dlya ruchnogo «pulsa» bez fonovogo potoka.
    """
    try:
        _STATE["last_scan"] = scan(root)
        _STATE["last_scan_ts"] = int(time.time())
        _STATE["ticks"] = int(_STATE["ticks"]) + 1
        _STATE["last_error"] = None
    except Exception as e:
        _STATE["last_error"] = f"{type(e).__name__}: {e}"
    return status()