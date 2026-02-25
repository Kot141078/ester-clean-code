# -*- coding: utf-8 -*-
"""AB Warden — edinyy “storozh” A/B-slotov i bezopasnogo avtokatbeka.

Mosty:
- Yavnyy: (Infrastruktura ↔ Moduli prilozheniy) - obschiy abstraktnyy mekhanizm A/B dlya vsekh podsistem.
- Skrytyy 1: (Nadezhnost ↔ Samoredaktura) - pri isklyucheniyakh v slote B vklyuchaetsya myagkiy otkat bez padeniya servisa.
- Skrytyy 2: (Nablyudaemost ↔ UX) — sostoyanie slota/otkat fiksiruetsya v state-fayle, dostupno interfeysu.

Zemnoy abzats:
Daem prostoy tumbler A/B dlya riskovannykh putey. Esli B dal sboy — avtomaticheski vozvraschaemsya k A i pishem zametku
v fayl sostoyaniya. Eto kak predokhranitel v elektroschite: srabotal - svet ne pogas, prosto vetka otklyuchilas."""
from __future__ import annotations

import os
import json
import time
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator, Optional, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True)
AB_STATE = STATE_DIR / "ab_state.json"


def _load_state() -> Dict[str, Any]:
    try:
        if AB_STATE.exists():
            return json.loads(AB_STATE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_state(d: Dict[str, Any]) -> None:
    try:
        AB_STATE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # does not interfere with work flow
        pass


def get_ab_mode(name: Optional[str] = None) -> str:
    """Returns the active slot (bAb|bb) for a specific module or globally.
    Priority: FOSIO_AB / ZZF0Z_AB -> AB_MODE -> bAb"""
    if name:
        v = os.getenv(f"{name.upper()}_AB") or os.getenv("PHYSIO_AB")  # example module-naming
        if v:
            return "B" if str(v).strip().upper().startswith("B") else "A"
    v = os.getenv("AB_MODE", "A")
    return "B" if str(v).strip().upper().startswith("B") else "A"


@contextmanager
def ab_switch(name: str) -> Iterator[str]:
    """
    Kontekst A/B s avtokatbekom.
    Ispolzovanie:
        with ab_switch("PHYSIO") as slot:
            if slot == "B":
                ... riskovannyy put ...
            else:
                ... nadezhnyy put ...
    """
    slot = get_ab_mode(name)
    st = _load_state()
    st.setdefault("modules", {}).setdefault(name, {})["last_enter"] = {"slot": slot, "ts": time.time()}
    _save_state(st)
    try:
        yield slot
        # success - celebrate
        st = _load_state()
        st.setdefault("modules", {}).setdefault(name, {})["last_ok"] = {"slot": slot, "ts": time.time()}
        _save_state(st)
    except Exception as e:
        # katbek pri B i razreshennom avtokatbeke
        if slot == "B" and (os.getenv("AB_AUTOROLLBACK", "1").strip() in {"1", "true", "yes"}):
            st = _load_state()
            rec = st.setdefault("modules", {}).setdefault(name, {})
            rec["last_fail"] = {"slot": slot, "ts": time.time(), "err": f"{type(e).__name__}:{e}"}
            rec["forced"] = "A"
            _save_state(st)
        # forward further - let the upper level decide (log/metric)
        raise


def get_ab_state() -> Dict[str, Any]:
    """Provides the aggregated state of A/B for UI/diagnostics."""
    d = _load_state()
    d["global"] = {"AB_MODE": get_ab_mode(None)}
    return d


# finalnaya stroka
# c=a+b