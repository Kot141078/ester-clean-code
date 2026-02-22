# -*- coding: utf-8 -*-
"""
modules/indexers/video_vector_indexer.py — eksport poslednikh video-konspektov/transkriptov v vektornoe khranilische.

Kak rabotaet (myagkaya integratsiya, drop-in):
  • Chitaet dampy ingest: data/video_ingest/rep_*.json (sm. VideoIngestCore pakety 01–05).
  • Formiruet elementy: {id, text, tags, meta}, gde text = summary || transcript (s chankingom).
  • Pytaetsya ispolzovat lokalnyy vektornyy stor (esli on u tebya uzhe est):
      - vstore_simple.VStore (chasto vstrechaetsya v tvoikh dampakh) — metod add/upsert (best-effort).
      - structured_memory.VectorStore / modules.memory.vector_store — esli prisutstvuet.
  • Esli podkhodyaschego stora net — pishet v fallback-ochered JSONL: data/video_ingest/vector_fallback.jsonl
    (ee mozhno podobrat tvoim suschestvuyuschim indeksatorom; format prostoy i stabilnyy).

Funktsii:
  - export_recent_to_vectors(limit=20, prefer_summary=True) -> dict
  - queue_size() -> int
  - fallback_path() -> str

Mosty:
- Yavnyy: (Memory ↔ Poisk) teksty popadayut v vektornyy sloy RAG → buduschie otvety Ester podkreplyayutsya faktami iz video.
- Skrytyy #1: (Infoteoriya ↔ Kibernetika) chanking stabiliziruet dlinu kontenta, snizhaet entropiyu indeksatora.
- Skrytyy #2: (Inzheneriya ↔ Nadezhnost) myagkie importy i fallback-ochered — indeksirovanie nikogda ne «lomaet» konveyer.

Zemnoy abzats:
Eto kak «ukladchik na polku kataloga»: beret gotovye otchety, narezaet kartochki i kladet v indeks; esli shkaf nedostupen —
skladyvaet v akkuratnuyu korobku (fallback), otkuda ikh mozhno rasstavit pozzhe.

# c=a+b
"""
from __future__ import annotations

import glob
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DATA_DIR = os.path.join(os.getcwd(), "data", "video_ingest")
FALLBACK_JSONL = os.path.join(DATA_DIR, "vector_fallback.jsonl")

def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _iter_recent(limit: int = 20) -> Iterable[str]:
    files = sorted(glob.glob(os.path.join(DATA_DIR, "rep_*.json")),
                   key=lambda p: os.path.getmtime(p), reverse=True)
    for p in files[: max(1, limit)]:
        yield p

def _chunks(text: str, size: int = 1200, overlap: int = 120) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    out: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        j = min(n, i + size)
        out.append(text[i:j])
        if j >= n:
            break
        i = j - overlap if (j - overlap) > i else j
    return out

def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path

def _write_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    _ensure_dir(os.path.dirname(path))
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def _now_id() -> str:
    return f"vidx_{int(time.time()*1000)}"

def _try_vstore_add(batch: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Probuet neskolko rasprostranennykh storadzhey. Vozvraschaet otchet ili None, esli nichego net.
    """
    # 1) vstore_simple
    try:
        import vstore_simple  # type: ignore
        vs = getattr(vstore_simple, "VStore", None)
        if vs is not None:
            store = vs(os.path.join("data", "vstore"))
            added = 0
            for it in batch:
                # podderzhivaem universalnye polya text/tags/meta
                text = it.get("text") or ""
                meta = it.get("meta") or {}
                tags = it.get("tags") or []
                # chasto vstrechaetsya add(text, meta)
                if hasattr(store, "add"):
                    store.add(text=text, meta={"tags": tags, **meta})
                elif hasattr(store, "upsert_texts"):
                    store.upsert_texts([{"text": text, "meta": {"tags": tags, **meta}}])
                added += 1
            return {"backend": "vstore_simple", "added": added}
    except Exception:
        pass

    # 2) structured_memory.VectorStore
    try:
        from structured_memory import VectorStore  # type: ignore
        vs = VectorStore()
        added = 0
        for it in batch:
            vs.add(text=it.get("text", ""), tags=it.get("tags", []), meta=it.get("meta", {}))
            added += 1
        return {"backend": "structured_memory.VectorStore", "added": added}
    except Exception:
        pass

    # 3) modules.memory.vector_store (obobschennyy interfeys)
    try:
        from modules.memory.vector_store import vector_upsert  # type: ignore
        vector_upsert([{"text": it.get("text", ""), "tags": it.get("tags", []), "meta": it.get("meta", {})} for it in batch])
        return {"backend": "modules.memory.vector_store", "added": len(batch)}
    except Exception:
        pass

    return None

def _build_items_from_dump(path: str, prefer_summary: bool = True) -> List[Dict[str, Any]]:
    j = _read_json(path) or {}
    src = (j.get("source") or {}).get("meta_json") or (j.get("source") or {}).get("local_path") or ""
    ts = int(Path(path).stem.split("_")[1]) if "_" in Path(path).stem else int(time.time())
    summary = (j.get("summary") or "").strip()
    transcript = ((j.get("transcript") or {}).get("text") or "").strip()
    items: List[Dict[str, Any]] = []
    base_meta = {
        "dump_path": path,
        "src": src,
        "ts": ts,
        "probe": j.get("probe", {}),
        "backend": (j.get("transcript") or {}).get("backend") or ""
    }
    # 1) summary (esli est i prefer_summary)
    if prefer_summary and summary:
        items.append({
            "id": f"{Path(path).stem}#sum",
            "text": summary,
            "tags": ["video", "summary"],
            "meta": base_meta
        })
    # 2) transcript chankingom
    for k, chunk in enumerate(_chunks(transcript)):
        items.append({
            "id": f"{Path(path).stem}#tr{k:03d}",
            "text": chunk,
            "tags": ["video", "transcript"],
            "meta": base_meta
        })
    return items

def export_recent_to_vectors(limit: int = 20, prefer_summary: bool = True) -> Dict[str, Any]:
    """
    Osnovnoy metod: vybiraet poslednie reporty, formiruet elementy i pytaetsya otpravit ikh v vektornyy stor.
    Esli stor nedostupen — pishet v fallback JSONL.
    """
    batch: List[Dict[str, Any]] = []
    picked: List[str] = []
    for p in _iter_recent(limit=limit):
        its = _build_items_from_dump(p, prefer_summary=prefer_summary)
        if its:
            batch.extend(its)
            picked.append(p)

    if not batch:
        return {"ok": True, "picked": 0, "indexed": 0, "backend": None, "fallback": FALLBACK_JSONL}

    rep = _try_vstore_add(batch)
    if rep:
        return {"ok": True, "picked": len(picked), "indexed": rep.get("added", 0), "backend": rep.get("backend"), "fallback": None}

    # fallback: skladyvaem v JSONL-ochered
    rows = [{"id": it["id"], "text": it["text"], "tags": it["tags"], "meta": it["meta"]} for it in batch]
    _write_jsonl(FALLBACK_JSONL, rows)
    return {"ok": True, "picked": len(picked), "indexed": 0, "backend": None, "fallback": FALLBACK_JSONL, "queued": len(rows)}

def queue_size() -> int:
    if not os.path.isfile(FALLBACK_JSONL):
        return 0
    try:
        with open(FALLBACK_JSONL, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def fallback_path() -> str:
    return FALLBACK_JSONL
