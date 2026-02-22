# -*- coding: utf-8 -*-
"""
modules/studio/prompts.py — generatsiya trendovykh promptov/stsenariev.

Mosty:
- Yavnyy: (LLM ↔ Kontent) sozdaet spisok idey/skriptov na baze tem/persony.
- Skrytyy #1: (Garazh ↔ Portfolio) mozhno dobavit kak proekt/artefakt.
- Skrytyy #2: (Volya ↔ Plan) ekshen mozhet zapuskatsya avtomaticheski.

Zemnoy abzats:
Eto «rybolovnye snasti» dlya idey: kompaktnye stsenarii, gotovye k ozvuchke i montazhu.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT=os.getenv("STUDIO_ROOT","data/studio")
OUT=os.getenv("STUDIO_OUT","data/studio/out")

def _ensure():
    os.makedirs(ROOT, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)

def _llm(prompt:str)->str:
    try:
        from modules.llm.broker import complete  # type: ignore
        rep=complete("lmstudio","gpt-4o-mini", prompt, max_tokens=700, temperature=0.5)
        if rep.get("ok"): return rep.get("text","")
    except Exception:
        pass
    return ""

PROMPT_TMPL = """Sgeneriruy 5 korotkikh stsenariev dlya {persona} po temam: {topics}.
Kazhdyy stsenariy: 1) zagolovok (<=60), 2) 3-5 tezisov (korotko), 3) call-to-action. Language: russkiy.
Format:
# <Title>
- tezis
...
CTA: ...
"""

def trending(topics: List[str], persona: str="ekspert") -> Dict[str,Any]:
    _ensure()
    prompt=PROMPT_TMPL.format(persona=persona, topics=", ".join(topics or ["tekhnologii"]))
    text=_llm(prompt) or f"# Ideya\n- {', '.join(topics)}\nCTA: Podpisyvaytes."
    fn=os.path.join(OUT, f"prompts_{int(time.time())}.md")
    open(fn,"w",encoding="utf-8").write(text)
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, text, {"kind":"prompts","persona":persona}, source="studio://prompts")
    except Exception:
        pass
    return {"ok": True, "path": fn, "length": len(text)}
# c=a+b