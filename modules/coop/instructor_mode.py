# -*- coding: utf-8 -*-
"""modules/coop/instructor_mode.py - “rezhim instruktora”: veduschiy vidit podtverzhdeniya vedomykh.

Ideaya:
- Veduschiy zapuskaet “klass”: spisok peers, ozhidanie “gotov” ot kazhdogo, zatem translyatsiya shagov.
- Vedomye otpravlyayut podtverzhdeniya shagov: {"peer":"ip:port","index":N,"ok":true|false,"latency_ms":...}
- Zhurnal: data/coop/instructor/log.jsonl

API:
- start_class(peers:list[str]) / stop_class()
- mark_ready(peer) — vedomyy gotov
- confirm(peer, index, ok, latency_ms)
- status() — gotovnost/poslednie podtverzhdeniya/svodka

MOSTY:
- Yavnyy: (Sovmestnost ↔ Kontrol) veduschiy vidit, chto realno proizoshlo u vedomykh.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) yavnye podtverzhdeniya + vremya otklika.
- Skrytyy #2: (Memory ↔ Analitika) JSONL-zhurnal dlya retrospektivy.

ZEMNOY ABZATs:
Bez brokerov; only REST. Logi - obychnyy JSONL. Ne vmeshivaetsya v uzhe rabotayuschiy pleybek/netpley.

# c=a+b"""
from __future__ import annotations
import os, json, time
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR  = os.path.join(ROOT, "data", "coop", "instructor")
os.makedirs(DIR, exist_ok=True)
LOG  = os.path.join(DIR, "log.jsonl")

_state: Dict[str, Any] = {
    "running": False,
    "peers": [],
    "ready": {},
    "last_confirms": [],  # [{peer,index,ok,latency_ms,ts}]
}

def _append(row: Dict[str, Any]) -> None:
    row["ts"] = int(time.time())
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def start_class(peers: List[str]) -> Dict[str, Any]:
    _state.update({"running": True, "peers": list(peers or []), "ready": {p: False for p in (peers or [])}, "last_confirms": []})
    _append({"event":"class_start","peers":_state["peers"]})
    return {"ok": True, **status()}

def stop_class() -> Dict[str, Any]:
    _append({"event":"class_stop"})
    _state.update({"running": False})
    return {"ok": True, **status()}

def mark_ready(peer: str) -> Dict[str, Any]:
    if peer not in _state.get("ready", {}):
        _state["ready"][peer] = True
    else:
        _state["ready"][peer] = True
    _append({"event":"ready","peer":peer})
    return {"ok": True, **status()}

def confirm(peer: str, index: int, ok: bool, latency_ms: int) -> Dict[str, Any]:
    rec = {"peer": peer, "index": int(index), "ok": bool(ok), "latency_ms": int(latency_ms)}
    _state["last_confirms"] = ([rec] + _state.get("last_confirms", []))[:100]
    _append({"event":"confirm","data":rec})
    return {"ok": True}

def status() -> Dict[str, Any]:
    ready = _state.get("ready", {})
    return {"ok": True, "running": bool(_state.get("running")), "peers": list(_state.get("peers", [])), "ready": ready, "ready_count": sum(1 for v in ready.values() if v), "confirms": _state.get("last_confirms", [])}