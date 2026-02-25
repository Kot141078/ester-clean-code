# -*- coding: utf-8 -*-
"""Runtime Watchdog - heartbeat, liveness/readiness, legkiy self-healing khuk.

Mosty:
- Yavnyy: (Servis ↔ Zdorove) — pishem heartbeat i otdaem agregirovannyy status dlya /health/*.
- Skrytyy 1: (A/B ↔ Nadezhnost) - v B-slote probe rashirnnye proverki (sensory), v A - minimalnyy set.
- Skrytyy 2: (Memory/Logi ↔ Diagnostika) — sostoyanie i poslednie sobytiya pishutsya v state-fayly.

Zemnoy abzats:
Eto “puls” servisa: raz v N sekund kladem otmetku “zhiv”, proveryaem bazovye podsistemy i soobschaem, gotov li on k rabote.
Esli chto-to ne tak — vidno srazu i v UI, i v JSON."""
from __future__ import annotations

import os, json, time, threading
from pathlib import Path
from typing import Dict, Any, Optional

from modules.meta.ab_warden import get_ab_state, ab_switch
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True)
HB_FILE = STATE_DIR / "heartbeat.json"

_watchdog_thread: Optional[threading.Thread] = None
_stop_flag = False

def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store  # type: ignore
            memory_add("dialog", text, meta=meta)
        except Exception:
            pass
        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if False:
                pass
        except Exception:
            pass
    except Exception:
        pass

def _snap_core() -> Dict[str, Any]:
    with ab_switch("HEALTH") as slot:
        # bazovyy puls + AB-sostoyanie
        data: Dict[str, Any] = {"ts": time.time(), "slot": slot, "ab": get_ab_state().get("global")}
        # advanced sensors - only in B, and if available
        if slot == "B":
            try:
                from modules.physio.sensors import snapshot
                data["sensors"] = snapshot().get("data")
            except Exception:
                data["sensors"] = None
        return data

def write_heartbeat() -> Dict[str, Any]:
    d = _snap_core()
    try:
        HB_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return {"ok": True, **d}

def read_heartbeat() -> Dict[str, Any]:
    try:
        if HB_FILE.exists():
            return {"ok": True, **json.loads(HB_FILE.read_text(encoding="utf-8"))}
    except Exception:
        pass
    return {"ok": False, "error": "no_heartbeat"}

def health_state() -> Dict[str, Any]:
    hb = read_heartbeat()
    now = time.time()
    live = hb.get("ok") and (now - float(hb.get("ts", 0))) < max(5.0, int(os.getenv("WATCHDOG_INTERVAL_SEC","10")) * 3)
    ready = bool(live)
    return {"ok": True, "live": bool(live), "ready": bool(ready), "since": hb.get("ts"), "ab": hb.get("ab"), "sensors": hb.get("sensors")}

def _loop(interval: int):
    global _stop_flag
    while not _stop_flag:
        write_heartbeat()
        time.sleep(max(1, interval))

def start_watchdog():
    """Yavnyy zapusk storozha (po umolchaniyu vklyuchen cherez ENV RUNTIME_WATCHDOG=1 - sm. register_all.py).
    Bez skrytykh sayd-effektov: zapusk initsiiruetsya registratorom na glazakh polzovatelya."""
    global _watchdog_thread, _stop_flag
    if _watchdog_thread and _watchdog_thread.is_alive():
        return
    _stop_flag = False
    t = threading.Thread(target=_loop, args=(int(os.getenv("WATCHDOG_INTERVAL_SEC", "10") or "10"),), daemon=True)
    t.start()
    _watchdog_thread = t
    try:
        _mirror_background_event(
            "[RUNTIME_WATCHDOG_START]",
            "runtime_watchdog",
            "start",
        )
    except Exception:
        pass

def stop_watchdog():
    global _stop_flag
    _stop_flag = True
    try:
        _mirror_background_event(
            "[RUNTIME_WATCHDOG_STOP]",
            "runtime_watchdog",
            "stop",
        )
    except Exception:
        pass

# finalnaya stroka
# c=a+b