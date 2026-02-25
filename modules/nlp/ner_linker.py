# -*- coding: utf-8 -*-
"""modules/nlp/ner_linker.py - legkiy izvlekatel suschnostey (NER) i linkovschik v KG/gipotezy.

How it works:
  • Pytaetsya spaCy ('en_core_web_sm' / 'xx_ent_wiki_sm'); esli net - padenie obratno na prostoy regeks-pravila.
  • Izvlekaet PERSON/ORG/LOC/DATE (best-effort), normalizuet v {type, value, span}.
  • Upsert v KG: pytaetsya importirovat modules.kg (ili /mem/kg/* kontrakt), inache — pishet v fallback JSONL.
  • Linki k gipotezam: esli peredan hypothesis_id, sozdaet svyaz (best-effort).

API (funktsii):
  - extract_entities(text: str) -> List[dict]
  - upsert_entities(entities: List[dict]) -> dict
  - link_hypothesis(hypothesis_id: str, entities: List[dict]) -> dict

Mosty:
- Yavnyy: (Memory ↔ KG) prevraschaem syrye teksty v uzly grafa znaniy.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) fallback JSONL isklyuchaet poteryu izvlechennykh suschnostey.
- Skrytyy #2: (Logika ↔ Memory) svyazi s gipotezami delayut obyasnimymi vyvody i retrival.

Zemnoy abzats:
This is “shtempelevschik” na priemke: na kazhdoy korobke pishet, kto/chto/gde/kogda, i kleit yarlyk s ID v grafe.

# c=a+b"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_FALLBACK_DIR = os.path.join("data", "kg")
os.makedirs(_FALLBACK_DIR, exist_ok=True)
_PEND_UPSERT = os.path.join(_FALLBACK_DIR, "pending_upserts.jsonl")
_PEND_LINKS = os.path.join(_FALLBACK_DIR, "pending_links.jsonl")

def _spacy_nlp():
    try:
        import spacy  # type: ignore
        for model in ("en_core_web_sm", "xx_ent_wiki_sm"):
            try:
                return spacy.load(model)
            except Exception:
                continue
    except Exception:
        pass
    return None

_NLP = _spacy_nlp()

def extract_entities(text: str) -> List[Dict[str, Any]]:
    text = (text or "").strip()
    ents: List[Dict[str, Any]] = []
    if not text:
        return ents
    if _NLP:
        doc = _NLP(text)
        for e in doc.ents:
            if e.label_ in ("PERSON", "ORG", "GPE", "LOC", "DATE"):
                ents.append({"type": e.label_, "value": e.text, "span": [e.start_char, e.end_char]})
        return ents
    # A simple falsification: PERSON/ORG as a sequence of words; DATE as YYYY or Montn YYYY
    cap_seq = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", text)
    for v in cap_seq:
        ents.append({"type": "NAME", "value": v, "span": []})
    for y in re.findall(r"\b(19|20)\d{2}\b", text):
        ents.append({"type": "DATE", "value": y, "span": []})
    return ents[:20]

def _kg_upsert_batch(rows: List[Dict[str, Any]]) -> bool:
    # Attempt 1: internal module KG
    try:
        from modules import kg  # type: ignore
        if hasattr(kg, "upsert_entities"):
            kg.upsert_entities(rows)
            return True
    except Exception:
        pass
    # Attempt 2: REST client (if reguest is available)
    try:
        import requests  # type: ignore
        requests.post("http://127.0.0.1:8000/mem/kg/upsert", json={"entities": rows}, timeout=2)
        return True
    except Exception:
        pass
    return False

def upsert_entities(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    ents = [e for e in entities if e.get("value")]
    if not ents:
        return {"ok": True, "upserted": 0}
    if _kg_upsert_batch(ents):
        return {"ok": True, "upserted": len(ents)}
    # fallback
    with open(_PEND_UPSERT, "a", encoding="utf-8") as f:
        for e in ents:
            f.write(json.dumps({"action": "kg.upsert", "entity": e}, ensure_ascii=False) + "\n")
    return {"ok": True, "upserted": 0, "queued": len(ents), "fallback": _PEND_UPSERT}

def link_hypothesis(hypothesis_id: str, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not hypothesis_id or not entities:
        return {"ok": True, "linked": 0}
    # Attempt 1: internal hypothesis module
    try:
        from modules import hypothesis  # type: ignore
        if hasattr(hypothesis, "link_entities"):
            hypothesis.link_entities(hypothesis_id, entities)
            return {"ok": True, "linked": len(entities)}
    except Exception:
        pass
    # Attempt 2: REST
    try:
        import requests  # type: ignore
        requests.post("http://127.0.0.1:8000/mem/hypothesis/link", json={"id": hypothesis_id, "entities": entities}, timeout=2)
        return {"ok": True, "linked": len(entities)}
    except Exception:
        pass
    # fallback
    with open(_PEND_LINKS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"action": "hyp.link", "id": hypothesis_id, "entities": entities}, ensure_ascii=False) + "\n")
# return {"ok": True, "linked": 0, "queued": len(entities), "fallback": _PEND_LINKS}