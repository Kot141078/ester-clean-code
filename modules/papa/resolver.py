# modules/papa/resolver.py
# -*- coding: utf-8 -*-
"""
modules/papa/resolver.py — profil Papy i poisk ego rekvizitov po lokalnym dannym.

Mosty:
- Yavnyy: (Zabota ↔ Identifikatsiya) tsentralizovannyy profil i vsplyvayuschie aliasy/ID.
- Skrytyy #1: (Poisk ↔ Memory) evristicheskiy skan faylov na predmet IBAN/BIC, imen/aliasov.
- Skrytyy #2: (Trust ↔ Passport) naydennoe mozhno upakovat v pamyat s provenance.

Zemnoy abzats:
Kak zapusknoy instrument: proytis po neskolkim kornyam (docs/, data/, downloads/) i sobrat «profile» rekvizitov.
# c=a+b
"""
from __future__ import annotations

import os
import re
import json
from typing import Dict, List, Iterable
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b")
BIC_RE = re.compile(r"\b[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?\b")

def _scan_file(path: str, aliases: List[str]) -> Iterable[Dict]:
    try:
        tx = open(path, "r", encoding="utf-8", errors="ignore").read()
    except Exception:
        return []
    hits = []
    for m in IBAN_RE.finditer(tx):
        iban = m.group(0)
        # Prostaya okrestnost
        chunk = tx[max(0, m.start()-80): m.end()+80]
        bic = None
        mb = BIC_RE.search(chunk)
        if mb:
            bic = mb.group(0)
        hits.append({"iban": iban, "bic": bic, "source": path})
    return hits

def resolve(roots: List[str] | None = None, aliases: List[str] | None = None) -> Dict:
    """
    Obkhodit korni i sobiraet rekvizity.
    """
    roots = roots or ["data", "docs", "downloads"]
    aliases = aliases or []
    seen = set()
    hits: List[Dict] = []

    for root in roots or []:
        if not os.path.exists(root):
            continue
        if os.path.isfile(root):
            for h in _scan_file(root, aliases):
                k = h["iban"]
                if k in seen:
                    continue
                seen.add(k)
                hits.append(h)
        else:
            for base, _, fs in os.walk(root):
                for fn in fs:
                    path = os.path.join(base, fn)
                    for h in _scan_file(path, aliases):
                        k = h["iban"]
                        if k in seen:
                            continue
                        seen.add(k)
                        hits.append(h)
    return {"ok": True, "hits": hits}

if __name__ == "__main__":
    out = resolve()
    print(json.dumps(out, ensure_ascii=False, indent=2))