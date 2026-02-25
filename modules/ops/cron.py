# -*- coding: utf-8 -*-
"""modules/ops/cron.py - planovye tekhprotsedury (heal→compact→snapshot→validate) pod “tik”.

Mosty:
- Yavnyy: (Raspisanie ↔ Routingi) obraschaetsya k uzhe suschestvuyuschim /mem/* i /index/* bez izmeneniya ikh kontraktov.
- Skrytyy #1: (AB-slot ↔ Bezopasnost) CRON_AB=B daet “sukhoy progon” bez vyzovov.
- Skrytyy #2: (Memory ↔ Profile) sokhranyaem profile-log o vypolnenii.

Zemnoy abzats:
Eto kak nochnoy klining v tsekhe: podmeli, smazali, proverili - morning vse krutitsya.

# c=a+b"""
from __future__ import annotations
import os, json, time, urllib.request
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("CRON_DB","data/ops/cron.json")
AB = (os.getenv("CRON_AB","A") or "A").upper()

DEFAULT_JOBS = [
    {"key":"mem.heal",     "every_sec": 24*3600, "url":"http://127.0.0.1:8000/mem/heal"},
    {"key":"mem.compact",  "every_sec": 24*3600, "url":"http://127.0.0.1:8000/mem/compact"},
    {"key":"mem.snapshot", "every_sec": 24*3600, "url":"http://127.0.0.1:8000/mem/snapshot"},
    {"key":"index.validate","every_sec":24*3600, "url":"http://127.0.0.1:8000/index/validate"}
]

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"last":{},"jobs":DEFAULT_JOBS}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _http_json(url: str)->Dict[str,Any]:
    req=urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def tick()->Dict[str,Any]:
    j=_load(); now=int(time.time())
    results=[]
    for job in j.get("jobs", DEFAULT_JOBS):
        key=job["key"]; every=int(job.get("every_sec", 24*3600))
        last=int(j.get("last",{}).get(key,0))
        due = now - last >= every
        ok=True; rep={"skipped": True}
        if due and AB=="A":
            try:
                rep=_http_json(job["url"])
            except Exception as e:
                ok=False; rep={"ok": False, "error": str(e)}
            j["last"][key]=now
        results.append({"key": key, "due": due, "ran": (due and AB=="A"), "rep": rep})
    _save(j)
    # profile
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, "CRON tick", {"results": [r["key"] for r in results], "AB": AB}, source="cron://ops")
    except Exception:
        pass
    return {"ok": True, "AB": AB, "results": results}
# c=a+b