# -*- coding: utf-8 -*-
"""
modules/cron/nightly.py — nochnye tekhprotsedury pamyati: heal→compact→snapshot.

Mosty:
- Yavnyy: (Memory/Indeksy ↔ Operatsii) svodim obsluzhivanie v odnu knopku/kron-zadachu.
- Skrytyy #1: (Profile ↔ Prozrachnost) rezultat po shagam fiksiruetsya.
- Skrytyy #2: (Survival ↔ Snapshoty) snapshot mozhno prevratit v bandl/torrent.

Zemnoy abzats:
Eto kak tekhobsluzhivanie v 3 chasa nochi: podkrutili, szhali, sfotografirovali — utrom vse bodro rabotaet.

# c=a+b
"""
from __future__ import annotations
import os, time, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE="data/cron/nightly_state.json"
os.makedirs(os.path.dirname(STATE), exist_ok=True)

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "cron://nightly")
    except Exception:
        pass

def _call(path: str, payload: dict|None=None, timeout: int=180)->dict:
    import urllib.request, json as _j
    data=None if payload is None else _j.dumps(payload or {}).encode("utf-8")
    req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return _j.loads(r.read().decode("utf-8"))

def run()->dict:
    steps=[]
    # 1) heal (esli est)
    try:
        rep=_call("/mem/heal", {})  # suschestvuet v tvoem dampe; esli net — budet except
        steps.append({"heal": rep})
    except Exception: steps.append({"heal":"skip"})
    # 2) compact
    try:
        rep=_call("/mem/compact", {})
        steps.append({"compact": rep})
    except Exception: steps.append({"compact":"skip"})
    # 3) snapshot (profile uzhe vedetsya; sdelaem survival bundle «mem_snapshot» best-effort)
    try:
        rep=_call("/survival/bundle/create", {"name":"mem_snapshot","include":["data/mem","data/passport"],"exclude":["*.lock","*.tmp"]})
        steps.append({"snapshot": rep})
    except Exception: steps.append({"snapshot":"skip"})
    st={"t": int(time.time()), "steps": steps}
    json.dump(st, open(STATE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    _passport("nightly_run", {"steps": len(steps)})
    return {"ok": True, "state": st}

def status()->dict:
    try:
        st=json.load(open(STATE,"r",encoding="utf-8"))
    except Exception:
        st={"t":0,"steps":[]}
    return {"ok": True, "state": st, "enabled": (os.getenv("CRON_NIGHTLY_ENABLE","true").lower()=="true"), "hour": int(os.getenv("CRON_NIGHTLY_HOUR","3") or "3")}
# c=a+b