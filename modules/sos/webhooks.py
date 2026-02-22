# -*- coding: utf-8 -*-
"""
modules/sos/webhooks.py — SOS-konfiguratsiya i vyzovy (webhook-first, bez integratsii s zakrytymi sistemami).

Mosty:
- Yavnyy: (Signaly ↔ Vebkhuki) universalnaya otpravka sobytiy v IFTTT/Make/Zapier/svoi servisy.
- Skrytyy #1: (Profile ↔ Trassirovka) fiksiruem fakty vyzovov/oshibok.
- Skrytyy #2: (RBAC ↔ Ostorozhnost) izmenenie konfiga — tolko dlya adminov.

Zemnoy abzats:
Eto kak «krasnaya knopka» s neskolkimi provodami: zaranee podklyuchili, a v nuzhnyy moment — odin vyzov.

# c=a+b
"""
from __future__ import annotations
import os, json, time, urllib.request
from typing import Any, Dict, List
from modules.media.utils import passport
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("SOS_DB","data/sos/config.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB): json.dump({"webhooks":[], "contacts":{}}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def set_config(cfg: Dict[str,Any])->Dict[str,Any]:
    j=_load()
    if "webhooks" in cfg: j["webhooks"]=list(cfg.get("webhooks") or [])
    if "contacts" in cfg: j["contacts"]=dict(cfg.get("contacts") or {})
    _save(j)
    passport("sos_config_set", {"w": len(j["webhooks"]), "c": len(j["contacts"])}, "sos://config")
    return {"ok": True}

def get_config()->Dict[str,Any]:
    j=_load()
    # klyuchi ne logiruem
    safe={"webhooks":[{"name":x.get("name",""), "url":"***"} for x in j.get("webhooks",[])], "contacts": j.get("contacts",{})}
    return {"ok": True, "config": safe}

def trigger(kind: str, note: str="")->Dict[str,Any]:
    j=_load(); out=[]
    payload={"t": int(time.time()), "kind": kind, "note": note, "contacts": j.get("contacts",{})}
    for wh in j.get("webhooks",[]):
        url=wh.get("url","")
        if not url: continue
        try:
            data=json.dumps(payload).encode("utf-8")
            req=urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                out.append({"name": wh.get("name",""), "code": r.getcode()})
        except Exception as e:
            out.append({"name": wh.get("name",""), "error": str(e)})
    passport("sos_trigger", {"kind": kind, "n": len(out)}, "sos://trigger")
    return {"ok": True, "sent": out}
# c=a+b