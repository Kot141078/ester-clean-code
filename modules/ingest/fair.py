# -*- coding: utf-8 -*-
"""modules/ingest/fair.py - per-source token-bucket + backoff dlya /ingest/submit (i pokhozhikh).

Mosty:
- Yavnyy: (Inzheneriya ↔ Spravedlivost) ogranichivaem rps/burst dlya kazhdogo istochnika.
- Skrytyy #1: (Nadezhnost ↔ Ocheredi) schitaem age i oshibki 429/5xx dlya avto-backoff.
- Skrytyy #2: (Nablyudaemost ↔ Metriki) otdaem svodku v /ingest/fair/status.

Zemnoy abzats:
“Gorlyshko butylki” regulirovat nado: so my ne utonem pod shkvalom zaprosov.

# c=a+b"""
from __future__ import annotations
import json, os, time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("INGEST_FAIR_AB","A") or "A").upper()
DIR = os.getenv("INGEST_FAIR_DIR","data/ingest")
DEF_RPS = float(os.getenv("INGEST_FAIR_DEFAULT_RPS","2") or "2")
DEF_BURST = int(os.getenv("INGEST_FAIR_DEFAULT_BURST","5") or "5")

def _ensure():
    os.makedirs(DIR, exist_ok=True)
    p = os.path.join(DIR,"quotas.json")
    if not os.path.isfile(p):
        json.dump({"default":{"rps": DEF_RPS, "burst": DEF_BURST}}, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _quotas() -> Dict[str,Any]:
    _ensure()
    return json.load(open(os.path.join(DIR,"quotas.json"),"r",encoding="utf-8"))

def set_quota(source: str, rps: float, burst: int) -> Dict[str,Any]:
    q = _quotas()
    q[source] = {"rps": float(rps), "burst": int(burst)}
    json.dump(q, open(os.path.join(DIR,"quotas.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "source": source, "quota": q[source]}

def _state_path(): return os.path.join(DIR,"buckets.json")
def _load_state() -> Dict[str,Any]:
    try: return json.load(open(_state_path(),"r",encoding="utf-8"))
    except Exception: return {}

def _save_state(st: Dict[str,Any]):
    json.dump(st, open(_state_path(),"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _tick(bucket: Dict[str,Any], rps: float, burst: int, now: float):
    last = float(bucket.get("last", now))
    tokens = float(bucket.get("tokens", burst))
    tokens = min(burst, tokens + (now - last) * rps)
    bucket["tokens"] = tokens
    bucket["last"] = now

def admit(source: str) -> Dict[str,Any]:
    """Returns ZZF0Z. In AB=B - always allow, we just log."""
    q = _quotas()
    conf = q.get(source) or q.get("default") or {"rps": DEF_RPS, "burst": DEF_BURST}
    st = _load_state()
    b = st.get(source) or {"tokens": conf["burst"], "last": time.time(), "age_first": 0, "denied": 0}
    now = time.time()
    _tick(b, conf["rps"], conf["burst"], now)
    allow = True
    retry = 0.0
    if AB == "A" and b["tokens"] < 1.0:
        allow = False
        retry = max(0.1, (1.0 - b["tokens"]) / max(0.1, conf["rps"]))
        b["denied"] = int(b.get("denied",0)) + 1
        if not b.get("age_first"): b["age_first"] = now
    else:
        b["tokens"] = max(0.0, b["tokens"] - 1.0)
        b["age_first"] = 0
    st[source] = b
    _save_state(st)
    return {"allow": allow, "retry_after": retry, "conf": conf, "ab": AB}

def mark_result(source: str, code: int):
    st = _load_state()
    b = st.get(source) or {}
    arr = b.get("codes",{})
    arr[str(code)] = int(arr.get(str(code),0)) + 1
    b["codes"] = arr
    st[source] = b
    _save_state(st)
    return {"ok": True}

def status() -> Dict[str,Any]:
    return {"ok": True, "quotas": _quotas(), "buckets": _load_state(), "ab": AB}
# c=a+b