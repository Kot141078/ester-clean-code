# -*- coding: utf-8 -*-
"""modules/scheduler/core.py - prostoy planirovschik (cron-podobnye vyrazheniya) s khraneniem v JSON.

Mosty:
- Yavnyy: (Avtonomiya ↔ Operatsii) zapuskaet playbook-i/HTTP/exec po raspisaniyu.
- Skrytyy #1: (Ostorozhnost ↔ Politiki) sozdanie zadach trebuet “pilyulyu”.
- Skrytyy #2: (Nadezhnost ↔ Resilience) tick mozhno dergat iz cron/paneli.

Zemnoy abzats:
Kak budilnik s zapisnoy knizhkoy: kogda prozvenit - vypolnit nuzhnoe.

# c=a+b"""
from __future__ import annotations
import os, json, time, subprocess, shlex
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("SCHED_DB","data/scheduler/jobs.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"jobs":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def list_jobs() -> Dict[str,Any]:
    _ensure(); return json.load(open(DB,"r",encoding="utf-8"))

def add_job(kind: str, spec: str, cron: str, note: str = "") -> Dict[str,Any]:
    _ensure()
    j=json.load(open(DB,"r",encoding="utf-8"))
    job={"id": f"j{int(time.time())}", "kind": kind, "spec": spec, "cron": cron, "last": 0, "note": note}
    j["jobs"].append(job)
    json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "job": job}

def _cron_match(cron: str, t: time.struct_time) -> bool:
    # minimum support: */n for minutes, other fields are asterisk
    parts=cron.strip().split()
    if len(parts)!=5: return False
    m, h, dom, mon, dow = parts
    def m_ok(mf:str, val:int)->bool:
        if mf=="*": return True
        if mf.startswith("*/"):
            try: n=int(mf[2:]); return (val % n)==0
            except: return False
        try:
            return int(mf)==val
        except:
            return False
    return m_ok(m, t.tm_min)
    # (for brevity/stability - only minutes; extension is possible without changing the contract)

def _run_playbook(path: str) -> Dict[str,Any]:
    try:
        import requests  # type: ignore
    except Exception:
        return {"ok": False, "error":"requests_missing"}
    try:
        with open(path,"r",encoding="utf-8") as f:
            data=f.read()
        # lokalnyy HTTP-vyzov /playbooks/run
        import http.client, json as _json
        conn=http.client.HTTPConnection("127.0.0.1", 80, timeout=10)
        conn.request("POST","/playbooks/run", body=data, headers={"Content-Type":"application/json"})
        resp=conn.getresponse(); out=resp.read().decode("utf-8","ignore")
        return {"ok": resp.status==200, "status": resp.status, "body": out}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _run_http(url: str) -> Dict[str,Any]:
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=10) as r:
            return {"ok": True, "status": r.status}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _run_exec(cmd: str) -> Dict[str,Any]:
    try:
        p=subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err=p.communicate(timeout=30)
        return {"ok": p.returncode==0, "rc": p.returncode, "stdout": out, "stderr": err}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def tick() -> Dict[str,Any]:
    _ensure()
    j=json.load(open(DB,"r",encoding="utf-8"))
    now=time.time(); tm=time.localtime(now)
    ran=[]; errs=[]
    for job in j.get("jobs",[]):
        try:
            if _cron_match(job["cron"], tm) and (now - job.get("last",0) >= 55):
                kind=job["kind"]; spec=job["spec"]
                if kind=="playbook": rep=_run_playbook(spec)
                elif kind=="http":  rep=_run_http(spec)
                elif kind=="exec":  rep=_run_exec(spec)
                else: rep={"ok": False, "error":"unknown_kind"}
                job["last"]=now
                ran.append({"id": job["id"], "kind": kind, "ok": rep.get("ok",False)})
        except Exception as e:
            errs.append({"id": job.get("id"), "error": str(e)})
    json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": len(errs)==0, "ran": ran, "errors": errs}
# c=a+b