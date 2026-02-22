# -*- coding: utf-8 -*-
"""
modules/finance/ledger.py — finansovyy ledzher (dokhody/raskhody, agregaty).

Mosty:
- Yavnyy: (Garazh/Marketpleysy ↔ Uchet) fiksiruem istochniki dokhodov (Patreon/YouTube/frilans) i traty.
- Skrytyy #1: (Profile ↔ Audit) klyuchevye operatsii mozhno zaveryat profilenoy zapisyu.
- Skrytyy #2: (LegalGuard ↔ Ostorozhnost) pered vneshnimi platezhami mozhno proveryat politiku.

Zemnoy abzats:
Eto «tetrad bukhgaltera»: kazhdaya kopeyka uchityvaetsya — otkuda prishla i kuda ushla — s bystrym itogom po kategoriyam.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("LEDGER_DB","data/finance/ledger.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB): json.dump({"items":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def upsert_item(rec: Dict[str,Any])->Dict[str,Any]:
    j=_load(); arr=j.get("items",[])
    item={
        "id": str(rec.get("id") or f"TX{int(time.time()*1000)}"),
        "type": str(rec.get("type","income")),  # income|expense
        "source": str(rec.get("source","misc")),
        "amount": float(rec.get("amount",0.0)),
        "currency": str(rec.get("currency","EUR")),
        "note": str(rec.get("note","")),
        "ts": int(time.time())
    }
    found=False
    for i,x in enumerate(arr):
        if x.get("id")==item["id"]: arr[i]=item; found=True; break
    if not found: arr.append(item)
    j["items"]=arr; _save(j)
    # profile (best-effort)
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        get_mm() and upsert_with_passport(get_mm(), "finance_upsert", {"id": item["id"], "type": item["type"], "amount": item["amount"], "src": item["source"]}, source="finance://ledger")
    except Exception: pass
    return {"ok": True, "item": item}

def list_items()->Dict[str,Any]:
    j=_load(); items=j.get("items",[])
    totals={"income":0.0,"expense":0.0}
    by_source={}
    for it in items:
        totals[it["type"]]+= float(it.get("amount",0.0))
        by_source.setdefault(it["source"], 0.0)
        by_source[it["source"]]+= float(it.get("amount",0.0)) * (1 if it["type"]=="income" else -1)
    balance= totals["income"] - totals["expense"]
    return {"ok": True, "items": items, "totals": totals, "balance": balance, "by_source": by_source}
# c=a+b