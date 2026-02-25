# -*- coding: utf-8 -*-
"""modules/guardian/contacts.py - doverennye kontakty i podgotovka eskalatsii (bez otpravki).

Mosty:
- Yavnyy: (Zabota ↔ Protsedury) khranit “komu mozhno zvonit/pisat” s yavnymi consent-flagami.
- Skrytyy #1: (Profile ↔ Audit) khuki dlya zapisi fakta eskalatsii.
- Skrytyy #2: (LegalGuard ↔ Bezopasnost) pered eskalatsiey mozhno zapuskat /policy/legal/check.

Zemnoy abzats:
Telefonnaya knizhka s krasnoy knopkoy: kto blizkiy, kak svyazatsya, chto imenno razresheno - i akkuratnaya podskazka, kak deystvovat.

# c=a+b"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("GUARDIAN_DB","data/guardian/contacts.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"contacts":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def upsert_contact(rec: Dict[str,Any])->Dict[str,Any]:
    j=_load(); arr=j.get("contacts",[])
    rec={
        "id": str(rec.get("id") or f"C{int(time.time())}"),
        "name": rec.get("name",""),
        "relation": rec.get("relation",""),
        "email": rec.get("email",""),
        "phone": rec.get("phone",""),
        "consent": dict(rec.get("consent") or {})  # {"emergency":bool, "financial":bool}
    }
    found=False
    for i,x in enumerate(arr):
        if x.get("id")==rec["id"]:
            arr[i]=rec; found=True; break
    if not found: arr.append(rec)
    j["contacts"]=arr; _save(j)
    return {"ok": True, "contact": rec}

def list_contacts()->Dict[str,Any]:
    j=_load(); return {"ok": True, "items": j.get("contacts",[])}

def prepare_escalation(kind: str, who_id: str, message: str)->Dict[str,Any]:
    """Returns instructions for manual sending: mailto:/sms:/call:.
    Sending fails."""
    j=_load(); target=None
    for c in j.get("contacts",[]):
        if c.get("id")==who_id: target=c; break
    if not target: return {"ok": False, "error":"contact_not_found"}

    cons=target.get("consent") or {}
    steps=[]
    if kind=="emergency" and cons.get("emergency"):
        if target.get("phone"):
            steps.append({"channel":"call","uri": f"tel:{target['phone']}", "note":"Pozvonit nemedlenno i kratko opisat situatsiyu."})
            steps.append({"channel":"sms","uri": f"sms:{target['phone']}?body={message}", "note":"Otpravit SMS s koordinatami/adresom pri vozmozhnosti."})
    if kind=="financial" and cons.get("financial"):
        if target.get("email"):
            steps.append({"channel":"email","uri": f"mailto:{target['email']}?subject=Ester%20Notice&body={message}", "note":"Pismo s detalyami i rekvizitami (IBAN i pr.)."})

    # profile (best-effort)
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, "guardian_escalate_prepare", {"kind":kind,"who":who_id,"steps":len(steps)}, source="guardian://escalate")
    except Exception:
        pass

    return {"ok": True, "to": target, "steps": steps, "message": message}
# c=a+b