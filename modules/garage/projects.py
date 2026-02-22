# -*- coding: utf-8 -*-
"""
modules/garage/projects.py — «garazh» proektov: reestr i prostoy bild (static site / bundle).

Mosty:
- Yavnyy: (Proekty ↔ Bild) khranit opisanie i stroit artefakty bez vneshnikh zavisimostey.
- Skrytyy #1: (Workbench/AutoDiscover ↔ Rasshirenie) gotovit fayly, kotorye mozhno srazu registrirovat.
- Skrytyy #2: (Ledzher ↔ Monetizatsiya) rezultaty mozhno poschitat/vystavit schet v posleduyuschem.

Zemnoy abzats:
Eto kak mini-stanok ChPU: dal zadanie — poluchil sayt/skript-sborku, kotoruyu mozhno otpravit zakazchiku.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB  = os.getenv("GARAGE_DB","data/garage/projects.json")
OUT = os.getenv("GARAGE_BUILD_DIR","data/garage/builds")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    if not os.path.isfile(DB): json.dump({"projects":[], "builds":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def upsert_project(rec: Dict[str,Any])->Dict[str,Any]:
    j=_load(); arr=j.get("projects",[])
    pid=str(rec.get("id") or f"P{int(time.time())}")
    obj={"id": pid, "kind": str(rec.get("kind","static_site")), "config": dict(rec.get("config") or {})}
    found=False
    for i,x in enumerate(arr):
        if x.get("id")==pid: arr[i]=obj; found=True; break
    if not found: arr.append(obj)
    j["projects"]=arr; _save(j)
    return {"ok": True, "project": obj}

def list_projects()->Dict[str,Any]:
    j=_load(); return {"ok": True, "items": j.get("projects",[])}

def _build_static_site(pid: str, cfg: Dict[str,Any])->Dict[str,Any]:
    title=cfg.get("title","Untitled")
    body =cfg.get("body","")
    d=os.path.join(OUT, pid); os.makedirs(d, exist_ok=True)
    html=f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title></head>
<body><h1>{title}</h1><div>{body}</div></body></html>"""
    path=os.path.join(d,"index.html")
    open(path,"w",encoding="utf-8").write(html)
    return {"dir": d, "files": ["index.html"]}

def _build_bundle(pid: str, cfg: Dict[str,Any])->Dict[str,Any]:
    d=os.path.join(OUT, pid); os.makedirs(d, exist_ok=True)
    files=[]
    for name, content in (cfg.get("files") or {}).items():
        p=os.path.join(d, name); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p,"w",encoding="utf-8").write(str(content)); files.append(name)
    return {"dir": d, "files": files}

def build_project(pid: str)->Dict[str,Any]:
    j=_load()
    proj=None
    for p in j.get("projects",[]):
        if p.get("id")==pid: proj=p; break
    if not proj: return {"ok": False, "error":"not_found"}
    kind=proj.get("kind","static_site"); cfg=proj.get("config") or {}
    if kind=="static_site":
        rep=_build_static_site(pid, cfg)
    else:
        rep=_build_bundle(pid, cfg)
    # uchet bilda
    b={"id": f"B{int(time.time())}", "project": pid, "dir": rep["dir"], "files": rep["files"], "ts": int(time.time())}
    j["builds"]= (j.get("builds") or []) + [b]; _save(j)
    # profile
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        get_mm() and upsert_with_passport(get_mm(), "garage_build", {"project":pid, "kind": kind, "files": rep["files"]}, source="garage://build")
    except Exception: pass
    return {"ok": True, "build": b}

def build_status()->Dict[str,Any]:
    j=_load(); return {"ok": True, "builds": j.get("builds",[])}
# c=a+b