# -*- coding: utf-8 -*-
"""
modules/ocr/lexicon_builder.py — personalnyy slovar UI-leksiki (OCR-praymer).

Istochniki:
- Zhurnal vnimaniya (/attention/journal) — zagolovki okon, metki shagov
- Podskazki iz /text_guess/guess — kandidaty slov (s indeksami uverennosti)

API:
- mine_from_journal(N=500) -> bag
- merge_guess(candidates[]) -> obnovit bag
- preview(top=200) -> tokeny/bigrammy s vesami
- export_json() -> perenosimyy JSON (dlya OCR komponentov sistemy)

MOSTY:
- Yavnyy: (Memory ↔ Raspoznavanie) personalnaya leksika dlya UI snizhaet oshibki OCR.
- Skrytyy #1: (Infoteoriya ↔ Ustoychivost) sglazhivanie chastot i otsechenie shumov.
- Skrytyy #2: (Inzheneriya ↔ Sovmestimost) chistyy perenosimyy format.

ZEMNOY ABZATs:
Bez vneshnikh modeley. Chastoty tokenov i bigramm, normalizatsiya registra.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import http.client, json, re, math, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"bag": {}, "bigrams": {}}

def _tok(s: str) -> List[str]:
    return [w for w in re.split(r"[^A-Za-zA-Yaa-ya0-9]+", s.lower()) if len(w) >= 3][:8]

def _get(path: str) -> Dict[str, Any]:
    conn=http.client.HTTPConnection("127.0.0.1",8000,timeout=12.0)
    conn.request("GET", path); r=conn.getresponse()
    t=r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def mine_from_journal(N: int = 500) -> Dict[str, Any]:
    j=_get(f"/attention/journal/list?n={int(max(50,N))}")
    bag=_state["bag"]; bi=_state["bigrams"]
    for it in j.get("items", []):
        for field in ("title","desc","hint","text"):
            s=str((it.get("detail") or {}).get(field,""))
            words=_tok(s)
            for w in words:
                bag[w]=bag.get(w,0)+1
            for a,b in zip(words, words[1:]):
                k=f"{a} {b}"; bi[k]=bi.get(k,0)+1
    return {"ok": True, "tokens": len(bag), "bigrams": len(bi)}

def merge_guess(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    bag=_state["bag"]; bi=_state["bigrams"]
    for c in candidates or []:
        w=str(c.get("text","")).lower().strip()
        if len(w)>=3:
            bag[w]=bag.get(w,0)+max(1, int(round(float(c.get("confidence",0.5))*2)))
    return {"ok": True}

def _top(d: Dict[str,int], k: int) -> List[Tuple[str,int]]:
    return sorted(d.items(), key=lambda x: -x[1])[:max(1,k)]

def preview(top: int = 200) -> Dict[str, Any]:
    return {"ok": True, "tokens": _top(_state["bag"], top), "bigrams": _top(_state["bigrams"], min(top, 100))}

def export_json() -> Dict[str, Any]:
    data={"exported_at": int(time.time()), "kind":"ui_lexicon", "tokens": _state["bag"], "bigrams": _state["bigrams"]}
    return {"ok": True, "lexicon": data}