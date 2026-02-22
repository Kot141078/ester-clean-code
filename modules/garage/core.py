# -*- coding: utf-8 -*-
"""
modules/garage/core.py — yadro «laboratorii-garazha» proektov.

Mosty:
- Yavnyy: (Proektnyy menedzhment ↔ FS/REST) sozdaem kartochki, scaffolding, eksport artefaktov.
- Skrytyy #1: (Memory ↔ Profile) vazhnye sobytiya logiruem v pamyat, podderzhivaya audit.
- Skrytyy #2: (Volya ↔ Eksheny) funktsii vyzyvayutsya kak rukami (REST), tak i mozgom (actions).

Zemnoy abzats:
Eto kak lichnyy garazh s verstakom: polki (indeks proektov), instrumenty (shablony), korobki (eksport ZIP).

# c=a+b
"""
from __future__ import annotations
import os, json, time, uuid, zipfile, hashlib
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT  = os.getenv("GARAGE_ROOT","data/garage")
DB    = os.getenv("GARAGE_DB","data/garage/index.json")
OUTBX = os.getenv("GARAGE_OUTBOX","data/garage/outbox")
TPLS  = os.getenv("GARAGE_TEMPLATES","data/garage/templates")

def _ensure():
    os.makedirs(ROOT, exist_ok=True)
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    os.makedirs(OUTBX, exist_ok=True)
    os.makedirs(TPLS, exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"projects":{}}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _mm_log(note:str, meta:Dict[str,Any])->None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, note, meta, source="garage://core")
    except Exception:
        pass

def _sha(s:str)->str:
    import hashlib; return hashlib.sha256((s or "").encode("utf-8")).hexdigest()

def create_project(name:str, kind:str="generic", brief:str="")->Dict[str,Any]:
    j=_load()
    pid=f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    path=os.path.join(ROOT, pid)
    os.makedirs(path, exist_ok=True)
    proj={"id":pid,"name":name,"kind":kind,"brief":brief,"created":int(time.time()),"path":path,"artifacts":[]}
    j["projects"][pid]=proj; _save(j)
    _mm_log(f"Sozdan proekt: {name}", {"id":pid,"kind":kind})
    return {"ok": True, **proj}

def list_projects()->Dict[str,Any]:
    j=_load(); xs=list(j.get("projects",{}).values())
    xs.sort(key=lambda r: r.get("created",0), reverse=True)
    return {"ok": True, "items": xs}

def get_project(pid:str)->Dict[str,Any]:
    j=_load(); p=j.get("projects",{}).get(pid)
    return {"ok": bool(p), "project": p}

def scaffold(pid:str)->Dict[str,Any]:
    j=_load(); p=j.get("projects",{}).get(pid)
    if not p: return {"ok": False, "error":"not_found"}
    base=p["path"]
    os.makedirs(os.path.join(base,"src"), exist_ok=True)
    os.makedirs(os.path.join(base,"docs"), exist_ok=True)
    os.makedirs(os.path.join(base,"site"), exist_ok=True)
    # shablon README
    rd=os.path.join(base,"README.md")
    if not os.path.isfile(rd):
        open(rd,"w",encoding="utf-8").write(f"# {p['name']}\n\nTip: {p['kind']}\n\n{p.get('brief','')}\n")
    _mm_log("Scaffold proekta", {"id":pid})
    return {"ok": True, "path": base}

def add_artifact(pid:str, rel_path:str, content:str)->Dict[str,Any]:
    j=_load(); p=j.get("projects",{}).get(pid)
    if not p: return {"ok": False, "error":"not_found"}
    ap=os.path.join(p["path"], rel_path)
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    open(ap,"w",encoding="utf-8").write(content)
    if rel_path not in p["artifacts"]:
        p["artifacts"].append(rel_path); _save(j)
    return {"ok": True, "path": ap}

def export_zip(pid:str)->Dict[str,Any]:
    j=_load(); p=j.get("projects",{}).get(pid)
    if not p: return {"ok": False, "error":"not_found"}
    zf=os.path.join(OUTBX, f"{pid}.zip")
    with zipfile.ZipFile(zf,"w",zipfile.ZIP_DEFLATED) as z:
        base=p["path"]
        for root,_,files in os.walk(base):
            for fn in files:
                fp=os.path.join(root,fn)
                z.write(fp, arcname=os.path.relpath(fp,base))
    _mm_log("Eksport proekta (ZIP)", {"id":pid,"zip":zf})
    return {"ok": True, "zip": zf, "sha256": _sha(open(zf,"rb").read().hex())}
# c=a+b