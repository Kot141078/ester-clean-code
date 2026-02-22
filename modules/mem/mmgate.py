# -*- coding: utf-8 -*-
"""
modules/mem/mmgate.py — «zhestkaya» tochka vkhoda k menedzheru pamyati + lint pryamykh obkhodov.

Mosty:
- Yavnyy: (Fabrika ↔ Metriki) schitaem obrascheniya cherez get_mm() i vyyavlyaem pryamye obkhody.
- Skrytyy #1: (Profile ↔ Prozrachnost) zapisyvaem fakty narusheniy/skanov.
- Skrytyy #2: (Rules/Cron ↔ Uluchsheniya) pravila mogut trebovat chistotu fabriki do zapuska payplaynov.

Zemnoy abzats:
Kak turniket na prokhodnoy: schitaem, kto proshel «kak polozheno», i lovim tekh, kto perelez cherez zabor.

# c=a+b
"""
from __future__ import annotations
import os, json, re, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("MMGATE_DB","data/mem/mmgate.json")
os.makedirs(os.path.dirname(DB), exist_ok=True)

def _load():
    if not os.path.isfile(DB):
        json.dump({"factory_calls":0,"direct_suspects":[],"last_scan":0}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return json.load(open(DB,"r",encoding="utf-8"))

def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def note_factory_call()->None:
    j=_load(); j["factory_calls"]=int(j.get("factory_calls",0))+1; _save(j)

def scan_sources(roots:list[str])->dict:
    """
    Best-effort: ischem patterny pryamoy initsializatsii VectorStore/Storage vmesto fabriki.
    Nichego ne lomaet — tolko otchet.
    """
    suspects=[]
    patt=re.compile(r"(new|init|=)\s*(VectorStore|Storage|SimpleMemory|Chroma|Lance)\s*\\(", re.I)
    for root in roots or []:
        for base,_,names in os.walk(root):
            for n in names:
                if not n.endswith(".py"): continue
                p=os.path.join(base,n)
                try:
                    src=open(p,"r",encoding="utf-8",errors="ignore").read()
                except Exception:
                    continue
                if patt.search(src):
                    suspects.append({"file": os.path.relpath(p,"."), "hit": True})
    j=_load(); j["direct_suspects"]=suspects; j["last_scan"]=int(time.time()); _save(j)
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp("mmgate_scan", {"suspects": len(suspects)}, "mem://mmgate")
    except Exception:
        pass
    return {"ok": True, "suspects": suspects, "n": len(suspects), "t": j["last_scan"]}

def status()->dict:
    j=_load()
    return {"ok": True, "factory_calls": int(j.get("factory_calls",0)), "suspects": j.get("direct_suspects") or [], "last_scan": int(j.get("last_scan",0))}
# c=a+b