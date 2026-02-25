# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.rag.answer - retrieve-then-summarize poverkh modules.rag.hub.

Mosty:
- Yavnyy: hub.search ↔ llm.broker.complete (if available).
- Skrytyy #1: (A/B) ESTER_RAG_ANSWER_AB - A: LLM, B: tolko ekstraktsiya.
- Skrytyy #2: (DX ↔ Prozrachnost) — vozvraschaem spisok tsitat (id, score) i ispolzovannyy rezhim.

Zemnoy abzats:
Prakticheskaya “otvetnaya duga”: berem blizkie fragmenty i kratko pereskazyvaem. Esli sintez nedostupen —
delaem chestnoe ekstraktivnoe rezyume, chtoby ne molchat.
# c=a+b"""
import os, textwrap
from typing import Dict, Any, List
from modules.rag import hub
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = os.getenv("ESTER_RAG_ANSWER_AB","A").upper().strip() or "A"
MAX_SNIPPETS = int(os.getenv("ESTER_RAG_ANSWER_MAX_SNIPPETS","5"))
MAX_CTX_CHARS = int(os.getenv("ESTER_RAG_ANSWER_MAX_CTX_CHARS","4000"))
STRICT = os.getenv("ESTER_RAG_ANSWER_STRICT","1") not in {"0","false","False"}

def _trim_ctx(items: List[Dict[str,Any]]) -> str:
    ctx_lines: List[str] = []
    used = 0
    for it in items[:max(1, MAX_SNIPPETS)]:
        t = (it.get("text") or "").strip()
        if not t:
            continue
        left = MAX_CTX_CHARS - used
        if left <= 0:
            break
        if len(t) > left:
            t = t[:left]
        ctx_lines.append(f"[{it.get('id')}|{float(it.get('score',0.0)):.3f}] {t}")
        used += len(t)
        if used >= MAX_CTX_CHARS:
            break
    return "\n".join(ctx_lines)

def _llm_summarize(q: str, ctx: str) -> str | None:
    try:
        from modules.llm import broker
        if not hasattr(broker, "complete"):
            return None
        sys = "You answer the question briefly and accurately based on the sources provided. If the answer is not in the sources, say so directly."
        prompt = textwrap.dedent(f"""
        [SYSTEM]
        {sys}

        [QUESTION]
        {q}

        [SOURCES]
        {ctx}

        [REPLY INSTRUCTIONS]
        - Otvet kratko (1-3 predlozheniya).
        - Ispolzuy fakty tolko iz [SOURCES].
        - V kontse dobav "refs: " i perechisli id istochnikov cherez zapyatuyu.
        """).strip()
        res = broker.complete(prompt)
        txt = res.get("text") if isinstance(res, dict) else str(res)
        return (txt or "").strip() or None
    except Exception:
        return None

def _extractive(q: str, items: List[Dict[str,Any]]) -> str:
    # simple safe squeeze without hallucinations
    tops = [f"- #{it.get('id')} ({float(it.get('score',0.0)):.3f}): { (it.get('text') or '').strip()[:200]}" for it in items[:max(1, MAX_SNIPPETS)]]
    head = "Answer by sources:"
    tail = "refs: " + ", ".join(str(it.get("id")) for it in items[:max(1, MAX_SNIPPETS)])
    return "\n".join([head] + tops + [tail])

def answer(q: str, k: int=5) -> Dict[str, Any]:
    sr = hub.search(q, max(1,k))
    items: List[Dict[str,Any]] = sr.get("items", [])
    if not items:
        return {"ok": False, "query": q, "items": [], "answer": "", "mode": "no_context", "ab": AB}
    ctx = _trim_ctx(items)
    ans: str | None = None
    mode = "extractive"
    if AB == "A":
        ans = _llm_summarize(q, ctx)
        if ans:
            mode = "llm"
    if not ans:
        ans = _extractive(q, items)
        mode = "extractive"
    return {
        "ok": True,
        "query": q,
        "items": [{"id": it.get("id"), "score": float(it.get("score",0.0))} for it in items],
        "answer": ans,
        "mode": mode,
        "ab": AB,
    }