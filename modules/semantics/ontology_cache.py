# -*- coding: utf-8 -*-
"""
Ontology Cache — keshiruyuschaya ontologiya ponyatiy (sinkhronizatsiya smyslov).

Mosty:
- Yavnyy: (Moduli ↔ Soglasovannyy slovar) — edinyy slovar terminov dlya vsekh chastey Ester.
- Skrytyy 1: (Memory ↔ Obyasnimost) — kazhdomu terminu soputstvuyut kanonicheskoe imya, sinonimy i kratkoe obyasnenie.
- Skrytyy 2: (Sovmestimost ↔ UX) — tekst mozhno «primirit» s ontologiey (reconcile) bez izmeneniya iskhodnykh moduley.

Zemnoy abzats:
Eto slovarik-«shpargalka»: «mem-obekt» = «zapis pamyati», «puls» = «signal» — i t.d.
Dalshe moduli menshe sporyat o terminakh, a otvety vyglyadyat rovnee.
"""
from __future__ import annotations

import os, json, re
from pathlib import Path
from typing import Dict, Any, List

from modules.meta.ab_warden import ab_switch
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True)
ONTO_FILE = STATE_DIR / "ontology.json"

def _load() -> Dict[str, Any]:
    try:
        if ONTO_FILE.exists():
            return json.loads(ONTO_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"terms": {}, "version": 1}

def _save(d: Dict[str, Any]) -> None:
    try:
        ONTO_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def define_term(name: str, definition: str, synonyms: List[str] | None = None) -> Dict[str, Any]:
    with ab_switch("SEMANTICS") as slot:
        db = _load()
        name_c = name.strip()
        db["terms"].setdefault(name_c, {"def": "", "syn": []})
        db["terms"][name_c]["def"] = definition.strip()
        if synonyms:
            syn = [s.strip() for s in synonyms if s and s.strip()]
            db["terms"][name_c]["syn"] = sorted(list(set((db["terms"][name_c]["syn"] or []) + syn)))
        _save(db)
        return {"ok": True, "slot": slot, "term": name_c}

def get_term(name: str) -> Dict[str, Any]:
    db = _load()
    t = db["terms"].get(name.strip())
    return {"ok": True, "term": name.strip(), "data": t, "file": str(ONTO_FILE)}

def list_terms(limit: int = 200) -> Dict[str, Any]:
    db = _load()
    keys = list(db["terms"].keys())[:limit]
    return {"ok": True, "count": len(db["terms"]), "terms": keys}

def reconcile_text(text: str) -> Dict[str, Any]:
    """
    Vozvraschaet normalizovannyy tekst i primenennye zameny na kanonicheskie terminy.
    """
    db = _load()
    mapping: Dict[str, str] = {}
    out = text or ""
    for name, payload in db["terms"].items():
        for syn in (payload.get("syn") or []):
            if not syn: 
                continue
            # slovo-granitsa, bez registrozavisimosti
            rx = re.compile(rf"(?<!\w){re.escape(syn)}(?!\w)", re.IGNORECASE)
            if rx.search(out):
                out = rx.sub(name, out)
                mapping[syn] = name
    return {"ok": True, "normalized": out, "applied": mapping}

# finalnaya stroka
# c=a+b