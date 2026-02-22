# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.rag.feedback — zhurnal RAG‑otvetov s myagkoy zapisyu v KG.

API:
- log(q: str, text: str, sources: list[dict]|None=None) -> dict
  Pishet sobytie v data/rag_feedback/events.jsonl i, esli vozmozhno, sozdaet suschnost v KG.

ENV:
- ESTER_RAG_FEEDBACK_AB=A|B — A: vklyucheno (po umolchaniyu), B: no‑op.

Mosty:
- Yavnyy: popytka ispolzovat modules.graph.* (add_entity/add_relation).
- Skrytyy #1: druzhit s modules.thinking.compat_actions.rag_answer (polya sovpadayut).
- Skrytyy #2: otchety cherez modules.reports.rag_feedback_http.

Zemnoy abzats:
Prakticheski — eto «nakleyka‑birka» na kazhdyy otvet: chto sprosili, chto otvetili, kakie byli istochniki.
# c=a+b
"""
import os, time, json, hashlib
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = os.getenv("ESTER_RAG_FEEDBACK_AB", "A").upper().strip() or "A"
DATA_DIR = os.path.join("data", "rag_feedback")
EVENTS = os.path.join(DATA_DIR, "events.jsonl")

def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

def _hash(s: str) -> str:
    import hashlib
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]

def _kg_iface():
    """
    Vozvraschaet (module, add_entity, add_relation) libo (None, None, None) esli KG nedostupen.
    Pytaemsya nayti v neskolkikh mestakh bez isklyucheniy naruzhu.
    """
    cand = ["modules.graph.kg", "modules.graph", "modules.kg"]
    for name in cand:
        try:
            m = __import__(name, fromlist=["*"])
            add_e = getattr(m, "add_entity", None)
            add_r = getattr(m, "add_relation", None)
            if callable(add_e) and callable(add_r):
                return m, add_e, add_r
        except Exception:
            pass
    return None, None, None

def log(q: str, text: str, sources: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if AB == "B":
        return {"ok": False, "skipped": True, "reason": "AB=B"}
    _ensure_dir()
    ts = int(time.time())
    q = (q or "").strip()
    text = (text or "").strip()
    sources = list(sources or [])
    eid = f"ans_{ts}_{_hash(q+text)}"
    ev = {"ts": ts, "id": eid, "q": q, "text": text, "sources": sources}
    # append to jsonl
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    # try KG
    kg, add_e, add_r = _kg_iface()
    kg_res = {"ok": False, "used": False}
    if kg and add_e and add_r:
        try:
            # Suschnost otveta
            props = {"len": len(text), "q": q, "ts": ts}
            r1 = add_e(eid, labels=["Answer"], props=props)  # type: ignore
            # Privyazyvaem istochniki, sozdavaya Doc‑uzly pri neobkhodimosti
            count = 0
            for s in sources[:8]:
                sid = s.get("id") or f"doc_{_hash((s.get('text') or '')[:64])}"
                stxt = (s.get("text") or "")[:400]
                add_e(sid, labels=["Doc"], props={"preview": stxt})
                add_r(eid, "DERIVED_FROM", sid)  # type: ignore
                count += 1
            kg_res = {"ok": True, "used": True, "linked": count}
        except Exception:
            kg_res = {"ok": False, "used": False}
    return {"ok": True, "event": ev, "kg": kg_res}

def tail(n: int = 20) -> Dict[str, Any]:
    """Poslednie n sobytiy (bez isklyucheniy pri otsutstvii fayla)."""
    _ensure_dir()
    items: List[Dict[str, Any]] = []
    try:
        with open(EVENTS, "r", encoding="utf-8") as f:
            lines = f.readlines()[-n:]
        for ln in lines:
            ln = (ln or "").strip()
            if not ln: continue
            try:
                items.append(json.loads(ln))
            except Exception:
                pass
    except FileNotFoundError:
        pass
    return {"ok": True, "items": items, "count": len(items)}