# -*- coding: utf-8 -*-
"""
modules/diagnostics/smoke_runner.py — HTTP smoke-progon klyuchevykh ruchek, otchet, status, reestr testov.

Mosty:
- Yavnyy: (Diagnostika ↔ Rantaym) bystryy «ping» podsistem i svodka.
- Skrytyy #1: (Cron/Hub ↔ Ekspluatatsiya) mozhno zapuskat po nocham i smotret otchet.
- Skrytyy #2: (Passport ↔ Prozrachnost) logi pingov i rezultatov.

Zemnoy abzats:
Kak kontrolnyy list pilota: «toplivo est, pribory goryat, shassi podnyato» — mozhno vzletat.

# c=a+b
"""
from __future__ import annotations
import os, json, time, urllib.request
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TESTS_FILE="data/tests/smoke.default.json"
STATE_FILE="data/tests/smoke.last.json"
os.makedirs("data/tests", exist_ok=True)

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "diag://smoke")
    except Exception:
        pass

def _load_tests()->List[Dict[str,Any]]:
    try:
        return json.load(open(TESTS_FILE,"r",encoding="utf-8")).get("tests",[])
    except Exception:
        return []

def _save_state(rep: dict)->None:
    json.dump(rep, open(STATE_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _call(method: str, path: str, payload: dict|None, timeout: int)->Dict[str,Any]:
    url="http://127.0.0.1:8000"+path
    t0=time.time()
    try:
        if method=="GET":
            with urllib.request.urlopen(url, timeout=timeout) as r:
                rt=r.read().decode("utf-8")
        else:
            data=json.dumps(payload or {}).encode("utf-8")
            req=urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                rt=r.read().decode("utf-8")
        dur=round(time.time()-t0,3)
        try: j=json.loads(rt)
        except Exception: j={"ok": True}
        ok=bool(j.get("ok", True))
        return {"path": path, "method": method, "ok": ok, "dur_s": dur, "rep": (j if ok else rt[:2000])}
    except Exception as e:
        dur=round(time.time()-t0,3)
        return {"path": path, "method": method, "ok": False, "dur_s": dur, "error": str(e)}

def run(fast: bool=False)->Dict[str,Any]:
    tests=_load_tests()
    if fast:
        # Bystryy podnabor
        tests=[t for t in tests if t.get("fast", True)]
    results=[]
    okn=0
    for t in tests:
        res=_call(t.get("method","GET"), t.get("path","/"), t.get("payload"), int(t.get("timeout",15)))
        res["name"]=t.get("name","")
        results.append(res)
        if res.get("ok"): okn+=1
        time.sleep(0.05)
    rep={"ok": all(r.get("ok") for r in results) if results else True, "total": len(results), "ok_n": okn, "time": int(time.time()), "results": results}
    _save_state(rep)
    _passport("smoke_run", {"ok": rep["ok"], "total": rep["total"], "ok_n": rep["ok_n"]})
    return rep

def status()->Dict[str,Any]:
    try:
        return json.load(open(STATE_FILE,"r",encoding="utf-8"))
    except Exception:
        return {"ok": True, "total": 0, "ok_n": 0, "time": 0, "results": []}

def list_tests()->Dict[str,Any]:
    return {"ok": True, "tests": _load_tests()}
# c=a+b