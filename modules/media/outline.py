# -*- coding: utf-8 -*-
"""
modules/media/outline.py — konspekt po subtitram/transkriptu: LLM + evristika v odnom flakone.

Mosty:
- Yavnyy: (LLM/Heuristics ↔ Kontent) — gibkiy vybor dlya szhatiya v tezisy.
- Skrytyy #1: (Nadezhnost ↔ Avtonomiya) — esli LLM spit, evristika bodrstvuet.
- Skrytyy #2: (KG ↔ Memory) — itog v pamyat, suschnosti v graf.

Zemnoy abzats:
Krupno rezhem video/tekst na glavy i punkty — bystro ponyat sut. Ester shutit: "Ya ne prosto konspekt, ya tvoy vtoroy mozg, tolko bez kofe-breykov."

# c=a+b
"""
from __future__ import annotations
import os, re, math, hashlib
from typing import Any, Dict, List
from collections import Counter
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _read_text(source: str) -> str:
    # Chitaem fayl, chistim SRT ot taymkodov — chtoby tekst byl svezhim, kak utrennyaya rosa.
    if not os.path.isfile(source): return ""
    text = open(source, "r", encoding="utf-8", errors="ignore").read()
    if source.lower().endswith(".srt"):
        text = re.sub(r"^\d+\s*$", "", text, flags=re.M)
        text = re.sub(r"\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}", "", text)
    return text.strip()

def _sentences(text: str) -> List[str]:
    # Razbivaem na predlozheniya — akkuratno, bez dramy.
    text = re.sub(r"\s+", " ", text)
    s = re.split(r"(?<=[.!?…])\s+", text)
    return [t.strip() for t in s if len(t.strip()) > 0]

def _score_sentences(sents: List[str]) -> List[float]:
    # Chastotnyy scoring: tf * (1 + pos) — prostota s namekom na genialnost.
    words = []; tokenized = []
    for s in sents:
        toks = re.findall(r"[A-Za-zA-Yaa-ya0-9']{3,}", s.lower())
        tokenized.append(toks); words += toks
    freq = Counter(words)
    scores = []
    n = len(sents)
    for i, toks in enumerate(tokenized):
        tf = sum(freq.get(w, 0) for w in toks) / (len(toks) or 1)
        pos = (i + 1) / max(1, n)
        scores.append(tf * (1.0 + 0.2 * pos))
    return scores

def _llm_outline(text: str, title: str = "") -> str:
    # LLM-volshebstvo: prosim szhat v bullets. Esli broker upal — molchim.
    try:
        from modules.llm.broker import complete  # type: ignore
    except Exception:
        return ""
    prompt = (f"Sdelay kratkiy strukturirovannyy konspekt s punktami (bullets) po tekstu subtitrov. "
              f"Sokhranyay lakonichnost, 10-15 punktov. Zagolovok: {title or 'Video'}.\n\n"
              f"Tekst:\n{text[:8000]}")
    rep = complete("lmstudio", "gpt-4o-mini", prompt, max_tokens=512, temperature=0.2)
    return (rep.get("text") or "").strip()

def _heur_outline(text: str, k: int = 12) -> str:
    # Evristika: scoring + top-K po khronologii. Grubaya, no nadezhnaya — kak staryy traktor.
    sents = _sentences(text)[:3000]  # Ne daem gigantam slomat nas.
    if not sents: return ""
    scores = _score_sentences(sents)
    idx = sorted(range(len(sents)), key=lambda i: -scores[i])[:k]
    idx.sort()  # Khronologiya — nashe vse.
    bullets = [f"- {sents[i].strip()}" for i in idx]
    return "\n".join(bullets)

def build_outline(text: str = "", source: str = "", title: str = "", mode: str = "auto", to_memory: bool = True, provenance: Dict[str, Any] | None = None, k: int = 12) -> Dict[str, Any]:
    # Universalnyyビルder: tekst ili fayl, LLM/heuristic/auto. Vozvraschaem dict s konspektom i plyushkami.
    if source:
        text = _read_text(source)
    text = (text or "").strip()
    if not text: return {"ok": False, "error": "empty_text"}
    
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    provenance = {**(provenance or {}), "sha256": sha}
    
    outline = ""
    if mode == "llm" or (mode == "auto" and (outline := _llm_outline(text, title))):
        pass  # LLM srabotal, ura!
    if not outline:  # Fallback na evristiku.
        outline = _heur_outline(text, k)
    
    kgl = {}
    try:
        from modules.mem.passport import upsert_with_passport  # type: ignore
        from services.mm_access import get_mm  # type: ignore
        from modules.kg.linker import extract as kg_ex, upsert_to_kg as kg_up  # type: ignore
        mm = get_mm()
        if to_memory and outline:
            meta = {"kind": "media_outline", "title": title, **provenance}
            upsert_with_passport(mm, outline, meta, source="media://outline")
        if text:
            ents = kg_ex(text).get("entities") or {}
            if ents:
                kg_up(ents, sha)
                kgl = {"entities": ents}
    except Exception:
        pass  # Tishe, Ester, pamyat podozhdet.
    
# return {"ok": True, "outline": outline, "sha256": sha, **kgl}