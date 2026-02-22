# -*- coding: utf-8 -*-
"""
modules/social/campaign.py — uchet kampaniy i avto-planirovanie iz assetov studii.

Mosty:
- Yavnyy: (Kampaniya ↔ Assety) khranenie kartochek i bystryy plan po platformam.
- Skrytyy #1: (Studiya ↔ Sotskit) nakhodit mp4/wav/ass i svyazyvaet s kampaniyami.
- Skrytyy #2: (Memory ↔ Profile) vazhnye sobytiya kladem v pamyat dlya audita.

Zemnoy abzats:
Kak belaya doska menedzhera: nazvanie, tsel, kakie roliki kuda i kogda.

# c=a+b
"""
from __future__ import annotations
import os, json, time, glob
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB   = os.getenv("SOCIAL_DB","data/social/index.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"campaigns":{}}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _mm_passport(note:str, meta:Dict[str,Any])->None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, note, meta, source="social://campaign")
    except Exception:
        pass

def create(title: str, goal: str="awareness")->Dict[str,Any]:
    j=_load()
    cid=f"C{int(time.time())}"
    j["campaigns"][cid]={"id":cid,"title":title,"goal":goal,"created":int(time.time()),"plans":[]}
    _save(j); _mm_passport("Sozdana kampaniya", {"id": cid, "title": title})
    return {"ok": True, "id": cid}

def plan(cid: str, sources: Dict[str,str], platforms: List[str], tags: List[str]|None=None)->Dict[str,Any]:
    """
    sources: {"studio_out":"data/studio/out"}
    platforms: ["tiktok","youtube_short","youtube_long","patreon_post"]
    """
    j=_load(); c=j["campaigns"].get(cid)
    if not c: return {"ok": False, "error":"not_found"}
    out_dir=(sources or {}).get("studio_out","data/studio/out")
    # nakhodim poslednie video
    vids=sorted(glob.glob(os.path.join(out_dir,"*.mp4")))
    auds=sorted(glob.glob(os.path.join(out_dir,"*.wav")))
    asses=sorted(glob.glob(os.path.join(out_dir,"*.ass")))
    assets={"video": vids[-1] if vids else "", "audio": auds[-1] if auds else "", "subs": asses[-1] if asses else ""}
    plan=[]
    for p in platforms or []:
        plan.append({"platform": p, "assets": assets, "tags": tags or []})
    c["plans"]=plan; _save(j)
    _mm_passport("Kampaniya splanirovana", {"id": cid, "plans": plan})
    return {"ok": True, "plans": plan}

def get(cid: str)->Dict[str,Any]:
    j=_load()
    return {"ok": cid in j.get("campaigns",{}), "campaign": j.get("campaigns",{}).get(cid)}
# c=a+b