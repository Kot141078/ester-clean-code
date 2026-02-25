# -*- coding: utf-8 -*-
"""Personal↔Global Bridge - agregator “lichnaya pamyat + vneshnie znaniya” s trustelnym prioritetom.

Mosty:
- Yavnyy: (Lichnaya pamyat ↔ Globalnye korpusa) - edinaya tochka zaprosa s ranzhirovaniem i folbekom offlayn.
- Skrytyy 1: (Doverie ↔ Vydacha) - Trust/Emotion povyshayut personalnye zapisi pri sortirovke.
- Skrytyy 2: (KG ↔ Ontologiya) — normalizatsiya terminov i svyazyvanie s uzlami KG dlya obyasnimosti.

Zemnoy abzats:
Odin vopros - dva karmana: v pervom - vashi zametki, vo vtorom - obschie znaniya.
Skladyvaem rezultaty i podnimaem naverkh to, chemu my bolshe doveryaem (i chto vam blizhe)."""
from __future__ import annotations

import os, json, math, hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple

from modules.meta.ab_warden import ab_switch
from modules.memory.trust_index import get_item as trust_get
from modules.memory.emotion_tagging import get as emotion_get
from modules.kg.symbolic_bridge import resolve as kg_resolve
from modules.semantics.ontology_cache import reconcile_text
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True)
PERS_FILE = STATE_DIR / "personal_corpus.jsonl"
GLOB_FILE = STATE_DIR / "global_corpus.jsonl"

def _read_jsonl(p: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line: 
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out

def _text_vec(text: str, dim: int = 48) -> List[float]:
    v = [0.0]*dim
    for tok in (text or "").lower().split():
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        v[h % dim] += 1.0
    norm = math.sqrt(sum(x*x for x in v)) or 1.0
    return [x/norm for x in v]

def _sim(a: List[float], b: List[float]) -> float:
    return sum(x*y for x,y in zip(a,b))

def query(q: str, topk: int = 5) -> Dict[str, Any]:
    """Single request: returns a mixed list of ZZF0Z.
    Slot B - adds CG results and more aggressive mixing."""
    q = (q or "").strip()
    if not q:
        return {"ok": False, "error": "empty_query"}
    qn = reconcile_text(q).get("normalized") or q
    qv = _text_vec(qn)
    with ab_switch("BRIDGE") as slot:
        # personal/global
        personal = _read_jsonl(PERS_FILE)
        global_ = _read_jsonl(GLOB_FILE)
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for rec in personal:
            txt = str(rec.get("text",""))
            pv = _text_vec(txt)
            base = _sim(qv, pv)
            trust = float((trust_get(rec.get("id","")).get("item") or {}).get("score", 0.0))
            affect = float((emotion_get(rec.get("id","")).get("item") or {}).get("affect", 0.0))
            bonus = 0.08*trust + 0.03*affect + 0.05  # personal nemnogo prioritetnee
            scored.append((base+bonus, {"source":"personal","text":txt,"id":rec.get("id")}))
        for rec in global_:
            txt = str(rec.get("text",""))
            gv = _text_vec(txt)
            base = _sim(qv, gv)
            scored.append((base, {"source":"global","text":txt,"id":rec.get("id")}))
        if slot == "B":
            kg = kg_resolve(qn, topk=topk).get("items") or []
            for it in kg:
                scored.append((it.get("score",0.0)+0.02, {"source":"kg","text":it.get("text"),"id":it.get("id")}))

        scored.sort(key=lambda x: x[0], reverse=True)
        out = [{"score": round(s,4), **rec} for s, rec in scored[:max(1, topk)]]
        return {"ok": True, "items": out}

# finalnaya stroka
# c=a+b