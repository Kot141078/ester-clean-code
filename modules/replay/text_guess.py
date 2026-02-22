# -*- coding: utf-8 -*-
"""
modules/replay/text_guess.py — «ugadyvanie» teksta dlya OCR-shagov iz sobytiy repleya.

Ideya:
- Nakhodim vremennye okna vokrug sobytiy tipa "ocr_ok"/"ocr_fail"/"template_ok".
- Iz zagolovkov/opisaniy sobytiy i evristik shagov formiruem kandidatov teksta (bez OCR!):
  * razbivaem desc na slova, filtruem korotkie, normalizuem registr
  * dobavlyaem evristicheskie slova: ["Fayl","Save","Save","Export","OK","OK","Apply"]
- Otsenivaem confidence po chastote/kontekstu (ochen grubaya metrika).

API:
- guess(events, window_ms=1200) -> [{"text":"Save","confidence":0.74,"window_ms":1200}, ...]

MOSTY:
- Yavnyy: (Memory ↔ Deystvie) predlagaem tekst dlya posleduyuschikh OCR-proverok.
- Skrytyy #1: (Infoteoriya ↔ Prostota) bez vneshnikh modeley/OCR — tolko statistika po sobytiyam.
- Skrytyy #2: (Inzheneriya ↔ UX) otdaem kompaktnyy spisok kandidatov.

ZEMNOY ABZATs:
Deshevaya evristika, rabotaet offlayn, idealno dlya bystrogo prototipa chekov.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
import math, re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE_HINTS = ["fayl","sokhranit","save","export","ok","ok","apply","eksport","pechat","print"]

def _tok(s: str) -> List[str]:
    return [w for w in re.split(r"[^A-Za-zA-Yaa-ya0-9]+", s.lower()) if len(w) >= 3]

def guess(events: List[Dict[str, Any]], window_ms: int = 1200) -> Dict[str, Any]:
    bag = {}
    for e in events or []:
        k = (e.get("kind") or "").lower()
        if k in ("ocr_ok","ocr_fail","template_ok"):
            desc = str(e.get("desc",""))
            for w in _tok(desc):
                bag[w] = bag.get(w,0)+1
    for h in BASE_HINTS:
        bag[h] = bag.get(h,0)+1
    total = sum(bag.values()) or 1
    cand = [{"text": t, "confidence": round((c/total)*1.5, 2), "window_ms": window_ms} for t,c in sorted(bag.items(), key=lambda x: -x[1])]
    # normalizuem diapazon doveriya
    for it in cand:
        it["confidence"] = float(min(0.95, max(0.2, it["confidence"])))
    # ostavim top-12
    return {"ok": True, "candidates": cand[:12]}