# -*- coding: utf-8 -*-
"""modules/cron/scheduler_light.py - “legkiy planirovschik”: nabor imenovannykh shagov i ruchnoy zapusk “nochnykh protsedur”.

Mosty:
- Yavnyy: (Operatsii ↔ Reglament) heal/compact/snapshot/validate + passport + kg_link.
- Skrytyy #1: (Nadezhnost ↔ Kontrol) bez skrytykh demonov: vse po yavnomu vyzovu.
- Skrytyy #2: (Vyzhivanie ↔ Memory) regulyarnaya gigiena ne daet indeksu “zarastat”.

Zemnoy abzats:
Eto kak nochnaya uborka: po knopke - podmesti, upakovat, proverit.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict, List
import os, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("CRON_AB","A") or "A").upper()

def _mm():
    try:
        from services.mm_access import get_mm  # type: ignore
        return get_mm()
    except Exception:
        return None

def _ok(name:str, detail: Any=None): return {"name": name, "ok": True, "detail": detail}
def _fail(name:str, detail: Any=None): return {"name": name, "ok": False, "detail": detail}

def heal() -> Dict[str,Any]:
    try:
        mm=_mm()
        if not mm: return _fail("heal","mm_unavailable")
        fn = getattr(mm,"heal", None)
        if not fn: return _ok("heal","noop")
        return _ok("heal", fn())
    except Exception as e:
        return _fail("heal", str(e))

def compact() -> Dict[str,Any]:
    try:
        mm=_mm(); 
        if not mm: return _fail("compact","mm_unavailable")
        fn = getattr(mm,"compact", None)
        if not fn: return _ok("compact","noop")
        return _ok("compact", fn())
    except Exception as e:
        return _fail("compact", str(e))

def snapshot() -> Dict[str,Any]:
    try:
        import requests, json  # type: ignore
    except Exception:
        return _fail("snapshot","requests_missing")
    try:
        # we use an existing handle from SelfPak packages
        r = requests.post("http://localhost:8000/self/pack/snapshot", json={"note":"nightly"}).json()
        return _ok("snapshot", r)
    except Exception as e:
        return _fail("snapshot", str(e))

def validate() -> Dict[str,Any]:
    try:
        import requests, json  # type: ignore
    except Exception:
        return _fail("validate","requests_missing")
    try:
        lst = requests.get("http://localhost:8000/self/pack/list").json()
        archs = [a.get("name") for a in (lst.get("items") or [])][-1:]
        rep=[]
        for a in archs:
            rep.append(requests.post("http://localhost:8000/self/pack/verify", json={"archive": a}).json())
        return _ok("validate", rep)
    except Exception as e:
        return _fail("validate", str(e))

def passport() -> Dict[str,Any]:
    try:
        from modules.memory.passport import sweep  # type: ignore
        return _ok("passport", sweep("*", 500))
    except Exception as e:
        return _fail("passport", str(e))

def kg_link() -> Dict[str,Any]:
    try:
        from modules.kg.linker import run  # type: ignore
        return _ok("kg_link", run(100))
    except Exception as e:
        return _fail("kg_link", str(e))

JOBS = ["heal","compact","snapshot","validate","passport","kg_link"]

def list_jobs() -> Dict[str,Any]:
    return {"ok": True, "jobs": JOBS, "ab": AB}

def run(names: List[str] | None = None) -> Dict[str,Any]:
    sels = [n for n in (names or JOBS) if n in JOBS]
    res=[]
    for n in sels:
        rep = globals()[n]()  # type: ignore
        res.append(rep)
    ok = all(r.get("ok") for r in res) if res else True
    return {"ok": ok, "results": res, "count": len(res)}
# c=a+b