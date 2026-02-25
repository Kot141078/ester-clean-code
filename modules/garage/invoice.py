# -*- coding: utf-8 -*-
"""modules/garage/invoice.py - invoysy (Markdown) i optsionalno SEPA pain.001 chernovik.

Mosty:
- Yavnyy: (Finansy ↔ Dokumenty) sozdaem ponyatnyy schet i pri zhelanii platezhnyy XML-chernovik.
- Skrytyy #1: (Memory ↔ Profile) fiksiruem vystavlenie invoysa.
- Skrytyy #2: (Volya ↔ Eksheny) dostupno cherez actions i REST.

Zemnoy abzats:
Schet - eto bumaga i rekvizity: odin fayl dlya chteniya chelovekom, vtoroy - dlya banka.

# c=a+b"""
from __future__ import annotations
import os, time, json
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

OUTBX=os.getenv("GARAGE_OUTBOX","data/garage/outbox")

def _passport(note:str, meta:Dict[str,Any])->None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, note, meta, source="garage://invoice")
    except Exception:
        pass

def _md_invoice(sender:Dict[str,Any], client:Dict[str,Any], items:List[Dict[str,Any]], currency:str)->str:
    total=sum(float(it.get("price",0))*float(it.get("qty",1)) for it in items)
    lines=["# Invoice",
           f"**Date:** {time.strftime('%Y-%m-%d')}",
           f"**From:** {sender.get('name','')}",
           f"**To:** {client.get('name','')}",
           f"**Currency:** {currency}",
           "\n## Items\n"]
    for it in items:
        lines.append(f"- {it.get('desc','')} — {it.get('qty',1)} × {it.get('price',0)} = {float(it.get('qty',1))*float(it.get('price',0))}")
    lines.append(f"\n**Total:** {total} {currency}\n")
    lines.append(f"\nIBAN: {sender.get('iban','')}  BIC: {sender.get('bic','')}\n")
    return "\n".join(lines)

def make_invoice(sender:Dict[str,Any], client:Dict[str,Any], items:List[Dict[str,Any]], currency:str="EUR", make_pain001:bool=False, end_to_end:str="", purpose:str="")->Dict[str,Any]:
    os.makedirs(OUTBX, exist_ok=True)
    md=_md_invoice(sender, client, items, currency)
    md_path=os.path.join(OUTBX, f"invoice_{int(time.time())}.md")
    open(md_path,"w",encoding="utf-8").write(md)
    out={"ok": True, "invoice_md": md_path}
    if make_pain001:
        try:
            from modules.finance.sepa import draft_pain001  # type: ignore
            amt=sum(float(it.get("price",0))*float(it.get("qty",1)) for it in items)
            pain = draft_pain001({"debtor": sender, "creditor": client, "amount": amt, "currency": currency, "purpose": purpose or "Freelance services", "end_to_end": end_to_end or f"ESTER-{int(time.time())}"})
            if pain.get("ok"): out["pain001"]=pain.get("path")
        except Exception:
            pass
    _passport("Vystavlen invoys", {"amount": sum(float(it.get("price",0))*float(it.get("qty",1)) for it in items), "currency": currency})
    return out
# c=a+b