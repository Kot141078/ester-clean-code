# -*- coding: utf-8 -*-
"""modules.subsonsious.engine - minimal offline subconscious engine (extension).
# c=a+b"""
from __future__ import annotations
import os, time, json
from dataclasses import dataclass, asdict
from typing import Dict, Any
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MEM_PATH = os.path.join(os.getcwd(), "data", "subconscious")
_state = {"enabled": True, "last_tick": 0}

def _log(ev: str, payload: Dict[str, Any] | None = None) -> None:
    base = Path(MEM_PATH); base.mkdir(parents=True, exist_ok=True)
    with open(base / "subconscious.log", "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": int(time.time()), "ev": ev, "data": payload or {}}, ensure_ascii=False) + "\n")

def status() -> Dict[str, Any]: return {"ok": True, **_state}
def enable() -> Dict[str, Any]: _state["enabled"]=True; _log("enable", _state.copy()); return status()
def disable() -> Dict[str, Any]: _state["enabled"]=False; _log("disable", _state.copy()); return status()
def tick_once() -> Dict[str, Any]: _state["last_tick"]=int(time.time()); _log("tick", _state.copy()); return {"ok": True, "tick": _state["last_tick"]}
def schedule() -> Dict[str, Any]: return {"ok": True, "scheduled": False}

@dataclass
class DreamMemory:
    id: str
    text: str
    tags: list[str]

def put_dream(dm: DreamMemory) -> Dict[str, Any]:
    base = Path(MEM_PATH) / "dreams"; base.mkdir(parents=True, exist_ok=True)
    with open(base / f"{dm.id}.json", "w", encoding="utf-8") as f:
        json.dump(asdict(dm), f, ensure_ascii=False, indent=2)
    _log("dream_put", {"id": dm.id}); return {"ok": True, "id": dm.id}

def _emit(event: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    _log(event, payload or {})
    return {"ok": True, "event": event}