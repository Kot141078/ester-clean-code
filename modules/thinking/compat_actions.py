# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.thinking.compat_actions — sovmestimye deystviya bez izmeneniya bazovogo yadra.

Ekshen: think.rag_answer
- Vyzov: rag_answer(q: str, top_k=3, mode='extractive')
- Vozvraschaet: dict {ok, text, mode, meta}
- Geyt: ESTER_THINK_RAG_AB (A/B)

Mosty:
- Yavnyy: most k modules.rag.answer / modules.rag.hub.
- Skrytyy #1: A/B flag ESTER_THINK_RAG_AB dlya bezopasnogo otkata.
- Skrytyy #2: pri nalichii registry — myagkaya registratsiya v action_registry.

Zemnoy abzats:
Prakticheski — eto «vstroennyy konsultant po pamyati»: izvlekaem fragmenty iz lokalnoy bazy i otvechaem s kratkoy vyzhimkoy.
# c=a+b
"""
import os
from typing import Dict, Any, Optional, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = os.getenv("ESTER_THINK_RAG_AB","A").upper().strip() or "A"

def _call_rag_answer(q: str, top_k:int=3, mode:str="extractive") -> str:
    """
    Pytaemsya vyzvat modules.rag.answer.answer; esli net — fallback na hub.search.
    """
    # Osnovnoy put
    try:
        from modules.rag import answer as ra  # type: ignore
        fn = getattr(ra, "answer", None)
        if callable(fn):
            return str(fn(q, top_k=top_k, mode=mode))  # sovmestimost s suschestvuyuschim modulem
    except Exception:
        pass
    # Fallback: hub.search + prostaya skleyka
    try:
        from modules.rag import hub  # type: ignore
        res = hub.search(q, k=top_k)  # ozhidaetsya {'items':[{'text':..., 'score':...}]}
        items = [it.get("text","") for it in (res.get("items") or [])]
        if not items:
            return "net relevantnykh fragmentov"
        # lakonichnyy otvet (1‑2 stroki)
        snippet = " ".join(items[:2])[:600]
        return f"Otvet po istochnikam: {snippet}"
    except Exception:
        return "RAG nedostupen"

def rag_answer(q: str, top_k:int=3, mode:str="extractive") -> Dict[str, Any]:
    if AB == "B":
        return {"ok": False, "skipped": True, "reason": "AB=B", "text": ""}
    q = str(q or "").strip()
    if not q:
        return {"ok": False, "error": "empty_query", "text": ""}
    text = _call_rag_answer(q, top_k=top_k, mode=mode)
    return {"ok": True, "text": text, "mode": mode, "meta": {"top_k": top_k, "len_q": len(q)}}

def heuristic_should_rag(q: str) -> bool:
    q = (q or "").strip()
    if not q: 
        return False
    # korotkie voprosy s voprositelnym znakom — tipichnyy sluchay RAG
    return (len(q) <= 240) and ("?" in q or len(q.split()) <= 24)

def try_register() -> Dict[str, Any]:
    """
    Pytaemsya myagko zaregistrirovat ekshen v suschestvuyuschem reestre deystviy.
    Sovmestimost: bez isklyucheniy pri otsutstvii reestra.
    """
    registered = False
    detail = "no_registry"
    try:
        from modules.thinking import action_registry as ar  # type: ignore
        reg = getattr(ar, "register", None) or getattr(ar, "register_action", None) or getattr(ar, "add", None)
        if callable(reg):
            # mnogie reestry ozhidayut imya i kollbek
            try:
                reg("think.rag_answer", rag_answer)  # type: ignore
            except TypeError:
                reg(name="think.rag_answer", fn=rag_answer)  # type: ignore
            registered = True
            detail = "registered"
    except Exception as e:
        detail = f"skip:{e.__class__.__name__}"
    return {"ok": True, "registered": registered, "detail": detail}