# -*- coding: utf-8 -*-
"""
IO Signals — bezopasnye fizicheskie signaly (LED/zvuk/virt.indikator) dlya otrazheniya sostoyaniya Ester.

Mosty:
- Yavnyy: (Servis ↔ Fizicheskiy mir) — preobrazuem logicheskie sobytiya v taktilnye/zvukovye/vizualnye signaly.
- Skrytyy 1: (Nadezhnost ↔ A/B) — riskovannye vyzovy ustroystv izolirovany v slote B, zapis v fayl — v A.
- Skrytyy 2: (Memory ↔ Diagnostika) — zhurnal signalov popadaet v state, viden UI i mozhet korrelirovat s logami.

Zemnoy abzats:
Eto «indikator na korpuse»: mignem, piknem ili prosto zapishem sobytie v fayl, chtoby chelovek ponyal — sistema zhiva,
dumaet, oshiblas ili zhdet vvoda. Na zheleze — GPIO/zummer; v softe — zhurnal s taym-autom (TTL).
"""
from __future__ import annotations

import os
import json
import time
import platform
from pathlib import Path
from typing import Dict, Any, List

from modules.meta.ab_warden import ab_switch, get_ab_state
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True)
SIG_FILE = STATE_DIR / "signals.json"


def _append_event(ev: Dict[str, Any]) -> None:
    arr: List[Dict[str, Any]] = []
    try:
        if SIG_FILE.exists():
            arr = json.loads(SIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        arr = []
    arr.append(ev)
    # ogranichim razmer
    if len(arr) > 2000:
        arr = arr[-500:]
    try:
        SIG_FILE.write_text(json.dumps(arr, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def pulse(level: str = "info", ttl_ms: int = 500) -> Dict[str, Any]:
    """
    Dat «impuls» indikatsii: info|warn|error, dlitelnost v ms.
    Slot A: tolko zhurnal v fayle.
    Slot B: pytaemsya «piknut» (Windows) ili sistemnyy zvukovoy signal, zatem tozhe zhurnal.
    """
    now = time.time()
    event = {
        "ts": now,
        "level": level,
        "ttl_ms": int(ttl_ms),
        "host": platform.node(),
    }
    with ab_switch("PHYSIO"):
        slot = os.getenv("PHYSIO_AB") or os.getenv("AB_MODE", "A")
        slot = "B" if str(slot).strip().upper().startswith("B") else "A"

        if slot == "B":
            # riskovannyy put — apparatnyy/sistemnyy zvuk, no bez vneshnikh deps
            try:
                if platform.system().lower().startswith("win"):
                    import winsound  # type: ignore
                    freq = 800 if level == "info" else (1200 if level == "warn" else 1600)
                    dur = max(100, min(int(ttl_ms), 2000))
                    winsound.Beep(freq, dur)
                else:
                    # POSIX: popytka sistemnogo «bell»
                    print("\a", end="", flush=True)  # mozhet byt otklyuchen terminalom — eto ok
            except Exception as e:
                event["note"] = f"signal_failed:{type(e).__name__}"

        _append_event(event)
        state = get_ab_state()
        return {"ok": True, "slot": slot, "event": event, "ab": state}


def read_state(limit: int = 50) -> Dict[str, Any]:
    try:
        arr = []
        if SIG_FILE.exists():
            arr = json.loads(SIG_FILE.read_text(encoding="utf-8"))
        if limit > 0:
            arr = arr[-limit:]
        return {"ok": True, "items": arr, "file": str(SIG_FILE)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}:{e}", "file": str(SIG_FILE)}


# finalnaya stroka
# c=a+b