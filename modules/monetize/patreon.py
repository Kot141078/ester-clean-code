# -*- coding: utf-8 -*-
"""
modules/monetize/patreon.py — generatsiya startovogo nabora Patreon (tiers + posty).

Mosty:
- Yavnyy: (Monetizatsiya ↔ Dokumenty) sozdaem JSON urovney i chernoviki postov dlya zagruzki.
- Skrytyy #1: (Memory ↔ Profile) fiksiruem fakt podgotovki kampanii.
- Skrytyy #2: (Garazh ↔ Portfolio) posty mogut ssylatsya na proekty/assety studii.

Zemnoy abzats:
Eto kak «startovyy paket» — urovni podderzhki i pervye posty uzhe lezhat na diske.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

OUT=os.getenv("STUDIO_OUT","data/studio/out")

def kit(creator: str, tiers: List[Dict[str,Any]], welcome: str, posts: List[Dict[str,Any]]|None=None)->Dict[str,Any]:
    os.makedirs(OUT, exist_ok=True)
    tj={"creator": creator, "tiers": tiers, "welcome": welcome}
    tpath=os.path.join(OUT, "patreon_tiers.json"); json.dump(tj, open(tpath,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    count=0
    for p in (posts or [{"title":"Dobro pozhalovat","body":welcome},{"title":"Za kulisami #1","body":"Pervyy shag: studiya gotova."}]):
        fn=os.path.join(OUT, f"patreon_post_{int(time.time())}_{count}.md")
        open(fn,"w",encoding="utf-8").write(f"# {p.get('title','')}\n\n{p.get('body','')}\n")
        count+=1
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, json.dumps(tj, ensure_ascii=False), {"kind":"patreon_kit"}, source="monetize://patreon")
    except Exception:
        pass
    return {"ok": True, "tiers_json": tpath, "posts": count}
# c=a+b