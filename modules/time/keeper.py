# -*- coding: utf-8 -*-
"""
modules/time/keeper.py — khranitel vremeni: otslezhivanie dreyfa chasov i zametki NTP/vneshnikh verifikatsiy.

Mosty:
- Yavnyy: (Vremya ↔ Nadezhnost) sravnivaem wall-clock s monotonikom mezhdu perezapuskami.
- Skrytyy #1: (Set ↔ Offlayn) rabotaem bez seti, no prinimaem zametki o vneshnikh proverkakh vremeni.
- Skrytyy #2: (Kripto ↔ Sroki) tochnost vremeni vazhna dlya TTL podpisey/priglasheniy (ConsentOps).

Zemnoy abzats:
Esli chasy «uplyvut», podpisi i sroki nachnut vrat. My eto lovim i signalim.

# c=a+b
"""
from __future__ import annotations
import json, os, time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TIME_AB = (os.getenv("TIME_AB","A") or "A").upper()
BEACON = os.getenv("TIME_BEACON","data/time/beacon.json")

def _ensure():
    os.makedirs(os.path.dirname(BEACON), exist_ok=True)
    if not os.path.isfile(BEACON):
        json.dump({"wall": int(time.time()*1000), "mono": int(time.perf_counter()*1000), "notes":[]}, open(BEACON,"w",encoding="utf-8"))

def status() -> Dict[str, Any]:
    _ensure()
    b = json.load(open(BEACON,"r",encoding="utf-8"))
    now_wall = int(time.time()*1000)
    now_mono = int(time.perf_counter()*1000)
    # ozhidaemyy wall po monotoniku
    elapsed = now_mono - int(b.get("mono", now_mono))
    expected = int(b.get("wall", now_wall)) + elapsed
    drift = now_wall - expected
    return {"ok": True, "now_wall_ms": now_wall, "drift_ms": drift, "notes": b.get("notes",[])}

def mark() -> Dict[str, Any]:
    _ensure()
    obj = {"wall": int(time.time()*1000), "mono": int(time.perf_counter()*1000)}
    st = json.load(open(BEACON,"r",encoding="utf-8"))
    obj["notes"] = st.get("notes",[])
    json.dump(obj, open(BEACON,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, **status()}

def note(source: str, offset_ms: int) -> Dict[str, Any]:
    _ensure()
    st = json.load(open(BEACON,"r",encoding="utf-8"))
    notes = st.get("notes",[])
    notes.append({"ts": int(time.time()*1000), "source": source, "offset_ms": int(offset_ms)})
    st["notes"] = notes
    json.dump(st, open(BEACON,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, **status()}
# c=a+b