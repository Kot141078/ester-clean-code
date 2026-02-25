# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.thinking.loop_full - minimalnaya upravlyalka tsikla myshleniya.
Mosty:
- Yavnyy: status()/start()/pause()/resume()/stop()/tick_once() — sinkhronnye rychagi dlya vneshnikh moduley.
- Skrytyy #1: (DX ↔ Nablyudaemost) — vozvraschaem strukturirovannyy status s taymshtampami.
- Skrytyy #2: (Signaly ↔ Shina) — publikuem sobytiya v modules.events_bus, esli dostupno.

Zemnoy abzats:
Dazhe esli “bolshoy” tsikl esche stroitsya, vneshnim komponentam nuzhny bazovye rychagi upravleniya.
This modul daet bezopasnye knopki: start/pauza/rezyum/stop, razovyy tik i status bez vneshnikh zavisimostey.
# c=a+b"""
import os
import time
from typing import Dict, Any, Optional, TypedDict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = [
    "status", "start", "pause", "resume", "stop", "tick_once"
]

class _Event(TypedDict, total=False):
    ts: int
    op: str
    reason: Optional[str]

AB = os.getenv("ESTER_THINKING_AB", "A").upper().strip() or "A"

_STATE: Dict[str, Any] = {
    "running": False,
    "paused": False,
    "ticks": 0,
    "last_event": None,        # type: Optional[_Event]
    # Launch options (compatibility with Ruthes/agent_loop_rutes.po)
    "goal": "",
    "interval_sec": 5,
    "max_steps": 50,
    "max_run_sec": 120,
    "idle_break_sec": 20,
    # Dop. telemetriya
    "ab": AB,
    "started_ts": None,        # type: Optional[int]
    "last_tick_ts": None,      # type: Optional[int]
}

def _emit(evt: str, payload: Dict[str, Any]) -> None:
    """Secure event publishing (bus may be missing)."""
    try:
        from modules import events_bus  # type: ignore
        if events_bus and hasattr(events_bus, "emit"):
            events_bus.emit(evt, payload)
    except Exception:
        # bus is not required
        pass

def _now() -> int:
    return int(time.time())

def status() -> Dict[str, Any]:
    """Current cycle status (no side effects)."""
    return {
        "ok": True,
        "running": bool(_STATE["running"]),
        "paused": bool(_STATE["paused"]),
        "ticks": int(_STATE["ticks"]),
        "last_event": _STATE["last_event"],
        "ab": AB,
        "ts": _now(),
        # debug fields
        "goal": _STATE["goal"],
        "interval_sec": _STATE["interval_sec"],
        "max_steps": _STATE["max_steps"],
        "max_run_sec": _STATE["max_run_sec"],
        "idle_break_sec": _STATE["idle_break_sec"],
        "started_ts": _STATE["started_ts"],
        "last_tick_ts": _STATE["last_tick_ts"],
    }

def start(
    goal: str = "manual",
    interval_sec: int = 5,
    max_steps: int = 50,
    max_run_sec: int = 120,
    idle_break_sec: int = 20,
) -> Dict[str, Any]:
    """Compatible signature under Rutes/agent_loop_rutes.po.
    We save the values ​​for observability; the cycle itself is tick-controlled."""
    _STATE["running"] = True
    _STATE["paused"] = False
    _STATE["ticks"] = 0
    _STATE["goal"] = str(goal or "")
    _STATE["interval_sec"] = int(interval_sec or 5)
    _STATE["max_steps"] = int(max_steps or 50)
    _STATE["max_run_sec"] = int(max_run_sec or 120)
    _STATE["idle_break_sec"] = int(idle_break_sec or 20)
    _STATE["started_ts"] = _now()
    _STATE["last_event"] = {"ts": _STATE["started_ts"], "op": "start", "reason": str(goal or "manual")}
    _emit("thinking.start", _STATE["last_event"])  # bridge to the event bus (if any)
    return status()

def pause(reason: str = "manual") -> Dict[str, Any]:
    if not _STATE["running"]:
        s = status()
        s["note"] = "not_running"
        return s
    _STATE["paused"] = True
    _STATE["last_event"] = {"ts": _now(), "op": "pause", "reason": reason}
    _emit("thinking.pause", _STATE["last_event"])
    return status()

def resume(reason: str = "manual") -> Dict[str, Any]:
    if not _STATE["running"]:
        s = status()
        s["note"] = "not_running"
        return s
    _STATE["paused"] = False
    _STATE["last_event"] = {"ts": _now(), "op": "resume", "reason": reason}
    _emit("thinking.resume", _STATE["last_event"])
    return status()

def stop(reason: Optional[str] = None) -> Dict[str, Any]:
    _STATE["running"] = False
    _STATE["paused"] = False
    _STATE["last_event"] = {"ts": _now(), "op": "stop", "reason": reason or "compat"}
    _emit("thinking.stop", _STATE["last_event"])
    return status()

def tick_once(reason: str = "manual") -> Dict[str, Any]:
    """Razovyy takt “myshleniya” - sovmestimyy eksport dlya routera.
    Po faktu - schetchik tikov i otmetki vremeni, chtoby instrumenty nablyudaemosti zhili uzhe seychas."""
    if not _STATE["running"]:
        s = status()
        s["note"] = "not_running"
        return s
    if _STATE["paused"]:
        s = status()
        s["note"] = "paused"
        return s
    _STATE["ticks"] = int(_STATE["ticks"]) + 1
    _STATE["last_tick_ts"] = _now()
    _STATE["last_event"] = {"ts": _STATE["last_tick_ts"], "op": "tick", "reason": reason}
    _emit("thinking.tick", _STATE["last_event"])
    return status()