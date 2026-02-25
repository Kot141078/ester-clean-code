# -*- coding: utf-8 -*-
"""Symbolic↔Neuro Bridge - most mezhdu “simvolicheskim” grafom znaniy i neyrourovnem (embedding-poiskom).

Mosty:
- Yavnyy: (Graf znaniy ↔ Embeddingi) - indeksiruem uzly KG i daem poisk po smyslu (vektornaya blizost).
- Skrytyy 1: (Doverie ↔ Ranzhirovanie) — uchityvaem TrustIndex/Emotion pri sortirovke rezultatov.
- Skrytyy 2: (Ontologiya ↔ Normalizatsiya) - soglasuem terminy cherez Ontology Cache pered zapisyu/poiskom.

Zemnoy abzats:
Eto “perekhodnik” mezhdu kartotekoy faktov (uzly/svyazi) i “chutem” po smyslu. Polozhili uzel - poschitali otpechatok,
potom bystro nakhodim blizkie po smyslu. Esli fakt trustennyy - podnimaem ego vyshe v vydache."""
from __future__ import annotations

import os, json, math, hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple

from modules.meta.ab_warden import ab_switch
from modules.memory.trust_index import get_item as trust_get
from modules.memory.emotion_tagging import get as emotion_get
from modules.semantics.ontology_cache import reconcile_text
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True)
KG_FILE = STATE_DIR / "kg_store.json"

def _load() -> Dict[str, Any]:
    try:
        if KG_FILE.exists():
            return json.loads(KG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"nodes": {}}  # id -> {"text":..., "emb":[...], "meta":{}}

def _save(db: Dict[str, Any]) -> None:
    try:
        KG_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _text_to_vec(text: str, dim: int = 64) -> List[float]:
    """Offline “embedding” without external dependencies: we hash tokens in a fixed vector (nashing feature)."""
    v = [0.0] * dim
    for tok in (text or "").lower().split():
        h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
        v[h % dim] += 1.0
    # L2-normirovka
    norm = math.sqrt(sum(x*x for x in v)) or 1.0
    return [round(x / norm, 6) for x in v]

def index_node(node_id: str, text: str, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Record/update CG node + offline vector.
    Slot A is a canned index. Slot B - rewrite the vector if the ID matches."""
    node_id = (node_id or "").strip()
    text = (text or "").strip()
    if not node_id or not text:
        return {"ok": False, "error": "bad_input"}
    # reconcile terminov
    text_norm = reconcile_text(text).get("normalized") or text
    with ab_switch("KG") as slot:
        db = _load()
        if slot == "A" and node_id in db["nodes"]:
            # we don’t touch the existing ones in A - just a meta update
            db["nodes"][node_id]["meta"] = {**(db["nodes"][node_id].get("meta") or {}), **(meta or {})}
        else:
            db["nodes"][node_id] = {
                "text": text_norm,
                "emb": _text_to_vec(text_norm),
                "meta": meta or {},
            }
        _save(db)
        return {"ok": True, "id": node_id, "slot": slot}

def resolve(text: str, topk: int = 5) -> Dict[str, Any]:
    """Search for the nearest nodes by meaning.
    The ranking takes into account trust/affect (if there are entries)."""
    q = (text or "").strip()
    if not q:
        return {"ok": False, "error": "empty_query"}
    qn = reconcile_text(q).get("normalized") or q
    qv = _text_to_vec(qn)
    db = _load()
    scored: List[Tuple[float, str, Dict[str, Any]]] = []
    for nid, rec in db["nodes"].items():
        # kosinusnoe skhodstvo
        dot = sum(a*b for a, b in zip(qv, rec.get("emb") or []))
        # doverie/emotsii
        trust = float((trust_get(nid).get("item") or {}).get("score", 0.0))
        affect = float((emotion_get(nid).get("item") or {}).get("affect", 0.0))
        bonus = 0.05 * trust + 0.02 * affect
        scored.append((dot + bonus, nid, rec))
    scored.sort(key=lambda x: x[0], reverse=True)
    items = [{"id": nid, "text": rec.get("text"), "score": round(s, 4)} for s, nid, rec in scored[:max(1, topk)]]
    return {"ok": True, "items": items}

def enrich(node_ids: List[str]) -> Dict[str, Any]:
    """Returns texts/meta from a list of node ids (a thin “symbolic” layer)."""
    db = _load()
    out = {}
    for nid in node_ids or []:
        if nid in db["nodes"]:
            out[nid] = db["nodes"][nid]
    return {"ok": True, "nodes": out}

# finalnaya stroka
# c=a+b