# -*- coding: utf-8 -*-
"""R4/services/reco/bslot_rerank.py - B-slot: rerank + short summary s pomoschyu lokalnogo LLM (LM Studio).
Avtokatbek: pri lyuboy oshibke LLM → vozvraschaem A-slot kak est s prostym ekstraktivnym summary.

Mosty:
- Yavnyy: Dzheynes — ispolzuem LLM kak "svidetelya" relevantnosti: on pereranzhiruet, povyshaya pravdopodobie topa.
- Skrytyy #1: Enderton — spetsifikatsiya vyvoda kak JSON-formuly (order/notes), kotoruyu legko validirovat.
- Skrytyy #2: Ashbi — regulyator prosche sistemy: esli slozhnyy B lomaetsya, vsegda est ustoychivyy A-kanal.

Zemnoy abzats:
Berem top-K iz A-slota (TF-IDF), peredaem kompaktnye snippety v LLM i prosim vernut chistyy JSON s
poryadkom (indeksy) i shortkimi summary (≤160 simvolov). Esli LLM ne otvechaet/nevaliden JSON —
ostavlyaem A-poryadok i delaem ekstraktivnye summary (pervye 160 simvolov). Only stdlib.

# c=a+b"""
from __future__ import annotations
import json
import os
from typing import List, Dict, Any

from services.reco.scorer_a import reco_score  # type: ignore
from services.reco.llm_client import LMStudioClient  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MAX_SUMMARY = 160

_SYSTEM_PROMPT = (
    "You are a concise and precise ranking. Input: user request and list of candidates"
    "(with indexes, quarrel_a and snippet). Sort candidates by relevance to the request and return"
    "ONLY JSION without comments of exactly this type:"
    "{\n"
    '"order": indexes in descending order of relevance,'
    '  "notes": {"<index>": "kratkoe rezyume (≤160 simv.)", "...": "..."}\n'
    "}\n"
    "No text except ZhSON. The summary is a snippet in content, without imagination or links."
)

def _extractive(text: str) -> str:
    s = (text or "").strip().replace("\n", " ")
    return (s[:MAX_SUMMARY] + ("…" if len(s) > MAX_SUMMARY else "")) or ""

def bslot_rerank(query: str, top: int = 5, tags: List[str] | None = None) -> List[Dict[str, Any]]:
    """
    Vozvraschaet spisok obektov:
    { score_a, score_b, meta{snippet,user,tags,ts}, summary }
    """
    topk = int(os.environ.get("R4_TOPK") or 8)
    cand = reco_score(query, top=max(topk, top), tags=tags or None)
    if not cand:
        return []

    # Prepare a list for the LLM
    items = []
    for i, c in enumerate(cand):
        meta = c.get("meta") or {}
        items.append({
            "idx": i,
            "score_a": float(c.get("score", 0.0)),
            "snippet": str(meta.get("snippet") or "")[:400],  # safety-ogranichenie
        })

    mode = (os.environ.get("R4_MODE") or "A").strip().upper()
    if mode != "B":
        # A-rezhim: bez LLM
        out = []
        for i, c in enumerate(cand[:top]):
            meta = c.get("meta") or {}
            out.append({
                "score_a": float(c.get("score", 0.0)),
                "score_b": float(c.get("score", 0.0)),  # net pereranzhirovaniya
                "meta": meta,
                "summary": _extractive(meta.get("snippet") or ""),
            })
        return out

    # B-rezhim: try LLM → pri sboe vozvraschaem A-fallback
    try:
        client = LMStudioClient()
        user_payload = {
            "query": query,
            "candidates": items,
            "instruction": "Verni tolko JSON (UTF-8)."
        }
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
        ]
        content = client.chat(messages=messages, max_tokens=600, temperature=0.2)
        js = json.loads(content)
        order = js.get("order") or []
        notes = js.get("notes") or {}
        # Validatsiya indeksov
        order = [int(i) for i in order if isinstance(i, int) or (isinstance(i, str) and i.isdigit())]
        order = [i for i in order if 0 <= i < len(cand)]
        if not order:
            raise ValueError("empty order")
        # Sobiraem vyvod
        out = []
        for i in order[:top]:
            c = cand[i]
            meta = c.get("meta") or {}
            summary = notes.get(str(i)) or notes.get(i) or _extractive(meta.get("snippet") or "")
            out.append({
                "score_a": float(c.get("score", 0.0)),
                "score_b": float(c.get("score", 0.0)) + 1e-6 * (len(out)+1),  # stabilnaya sortirovka, bez alk.
                "meta": meta,
                "summary": str(summary)[:MAX_SUMMARY],
            })
        return out
    except Exception:
        # Avtokatbek → A
        out = []
        for i, c in enumerate(cand[:top]):
            meta = c.get("meta") or {}
            out.append({
                "score_a": float(c.get("score", 0.0)),
                "score_b": float(c.get("score", 0.0)),
                "meta": meta,
                "summary": _extractive(meta.get("snippet") or ""),
            })
        return out