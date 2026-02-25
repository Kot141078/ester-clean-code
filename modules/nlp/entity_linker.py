# -*- coding: utf-8 -*-
"""modules/nlp/entity_linker.py - legkaya avto-linkovka suschnostey (PERSON/ORG/LOC/DATE) i upsert v KG.

Funktsii:
  • extract_entities(text:str) -> list[dict] # [{"type":"PERSON","value":"Alan Turing"}, ...]
  • upsert_entities(ents:list[dict]) -> dict # {"ok":True,"upserted":N}
  • link_text(text:str, upsert:bool=True) -> dict

Realizatsiya:
  • Bez vneshnikh zavisimostey: regeksp-evristiki + prostaya filtratsiya, prigodno dlya fallback.
  • Esli spaCy/Stanza dostupny - mozhno rasshirit (no tut ne trebuetsya).

Mosty:
- Yavnyy: (KG ↔ Memory) avtomaticheski sozdaem/obnovlyaem uzly grafa i daem gipotezam ssylki.
- Skrytyy #1: (Infoteoriya ↔ RAG) normalizovannyy slovar suschnostey povyshaet kachestvo retriva.
- Skrytyy #2: (Inzheneriya ↔ Ustoychivost) modul ne trebuet tyazhelykh NLP — podkhodit dlya oflayna.

Zemnoy abzats:
This is “shtempelevschik imen”: vidit lyudey/organizatsii/mesta/daty i kladet ikh v katalog.

# c=a+b"""
from __future__ import annotations

import re
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def extract_entities(text: str) -> List[Dict[str, str]]:
    ents: List[Dict[str, str]] = []
    if not (text or "").strip():
        return ents
    # PERSONS (very rudely: Two Capital Letters)
    for m in re.finditer(r"\b([A-ZA-YaE][a-za-yae]+(?:\s+[A-ZA-YaE][a-za-yae]+)+)\b", text):
        val = m.group(1).strip()
        if len(val.split()) <= 4:
            ents.append({"type": "PERSON", "value": val})
    # ORG (glavnye slova)
    for m in re.finditer(r"\b(University|Institute|Laboratory|Lab|Company|Inc\.|Ltd\.|OOO|NII|GUP|AO|MGU|SPbGU|MIT|IBM)\b", text, flags=re.I):
        ents.append({"type": "ORG", "value": m.group(1)})
    # LOC (prostye toponimy)
    for m in re.finditer(r"\b(London|Cambridge|Moscow|Paris|New York|Berlin|Bletchli|Moskva|Parizh|Berlin)\b", text, flags=re.I):
        ents.append({"type": "LOC", "value": m.group(1)})
    # DATE (gody)
    for m in re.finditer(r"\b(19\d{2}|20\d{2})\b", text):
        ents.append({"type": "DATE", "value": m.group(1)})
    # unikaliziruem
    seen = set(); out: List[Dict[str, str]] = []
    for e in ents:
        key = (e["type"], e["value"].lower())
        if key in seen:
            continue
        seen.add(key); out.append(e)
    return out

def upsert_entities(ents: List[Dict[str, str]]) -> Dict[str, Any]:
    """Best-effort: calls /them/kg/upsert (if any) or put it in a false log.
    We do not change contracts of old pens."""
    n = 0
    try:
        # Predpolagaem nalichie standartnogo KG-interfeysa
        import requests  # typical in the environment, if not - just false
        import os
        base = os.getenv("ESTER_BASE_URL", "http://127.0.0.1:8000")
        url = f"{base}/mem/kg/upsert"
        payload = {"nodes": [{"type": e["type"], "value": e["value"]} for e in ents]}
        r = requests.post(url, json=payload, timeout=3)
        if r.status_code == 200:
            n = len(ents)
            return {"ok": True, "upserted": n, "mode": "remote"}
    except Exception:
        pass
    # fallback: lokalnyy fayl
    try:
        import json, os
        os.makedirs("data/kg_fallback", exist_ok=True)
        with open("data/kg_fallback/upserts.jsonl", "a", encoding="utf-8") as f:
            for e in ents:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        n = len(ents)
        return {"ok": True, "upserted": n, "mode": "fallback"}
    except Exception:
        return {"ok": False, "error": "cannot upsert"}

def link_text(text: str, upsert: bool = True) -> Dict[str, Any]:
    ents = extract_entities(text)
    rep = {"ok": True, "entities": ents}
    if upsert and ents:
        rep["upsert"] = upsert_entities(ents)
# return rep