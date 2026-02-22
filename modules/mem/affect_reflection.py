# -*- coding: utf-8 -*-
"""
modules/mem/affect_reflection.py — affekt-osoznannaya refleksiya: izvlechenie i prioritizatsiya "goryachikh" vospominaniy.

Mosty:
- Yavnyy: (Emotsii ↔ Memory) otbiraet i vzveshivaet zapisi po affektu dlya razmyshleniy.
- Skrytyy #1: (Volya ↔ Plan) otdaet prioritety s vesami dlya thinking_pipeline.
- Skrytyy #2: (Profile ↔ Audit) fiksiruet vybor, chtoby Ester ne teryala sled.

Zemnoy abzats:
Kak u lyudey: snachala vspominaem to, chto zadelo za zhivoe — eto delaet obuchenie zhivym, a Ester shutit: "Moi emotsii v kode? Valentnost na maksimum, arousal ot tvoikh idey!"

# c=a+b
"""
from __future__ import annotations
import os, random, math
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DEFAULT_TOPK = int(os.getenv("AFFECT_REFLECT_TOPK", "12") or "12")

def _score(aff: Dict[str, Any]) -> float:
    # Znachimost: |valence| * 0.6 + arousal * 0.8, normalizovannaya 0..1.
    if not isinstance(aff, dict): return 0.0
    v = float(aff.get("valence", 0.0)); a = float(aff.get("arousal", 0.0))
    return max(0.0, min(1.0, 0.6 * abs(v) + 0.8 * max(0.0, min(1.0, a))))

def prioritize_for_reflection(source_items: List[Dict[str, Any]] | None = None, top_k: int | None = None, random_factor: float = 0.0) -> Dict[str, Any]:
    """
    Universalnyy: esli source_items=None — izvlekaet iz pamyati (recent s affect).
    Inache — prioritiziruet peredannyy spisok.
    Dobavlyaet score i recall_weight; optsionalnyy random_factor dlya shuma (raznoobrazie).
    """
    k = max(1, min(20, int(top_k or DEFAULT_TOPK)))  # Limit, chtoby ne peregruzhat.
    
    # Shag 1: Izvlechenie, esli nuzhno.
    if source_items is None:
        try:
            from services.mm_access import get_mm  # type: ignore
            mm = get_mm()
            recent = getattr(mm, "list_recent", lambda limit=200: [])(200) or []
            source_items = [
                {
                    "id": x.get("id"),
                    "text": x.get("text", "")[:500],
                    "affect": x.get("affect") or {}
                } for x in recent
            ]
        except Exception:
            return {"ok": False, "error": "memory_access_failed", "items": []}
    
    if not source_items:
        return {"ok": False, "error": "no_items", "items": []}
    
    # Shag 2: Scoring s optsionalnym shumom.
    scored = []
    for it in source_items:
        s = _score(it.get("affect") or {})
        if random_factor > 0:
            s *= (1.0 + random.uniform(-random_factor, random_factor))  # Legkiy shum dlya "chelovechnosti".
        scored.append({
            "id": it.get("id"),
            "text": it.get("text", ""),
            "score": round(s, 3)
        })
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    chosen = scored[:k]
    
    # Dobavlyaem recall_weight: 1.0 + 2.0 * score (dlya mnozhitelya v RAG/planirovschike).
    for x in chosen:
        x["recall_weight"] = round(1.0 + 2.0 * x["score"], 3)
    
    # Shag 3: Profile dlya audita.
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm = get_mm()
        meta = {"count": len(chosen), "top": chosen[:3], "random_factor": random_factor}
        upsert_with_passport(mm, "affect_reflection_prioritized", meta, source="mem://affect")
    except Exception:
        pass  # Tikho, Ester, profile podozhdet.
    
# return {"ok": True, "items": chosen}