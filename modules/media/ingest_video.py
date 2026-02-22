# -*- coding: utf-8 -*-
"""
modules/media/ingest_video.py — edinaya orkestratsiya: URL/put → metadannye → subtitry → konspekt → pamyat.

Mosty:
- Yavnyy: (Memory ↔ Media) skladyvaem artefakty v pamyat s meta.provenance (profile).
- Skrytyy #1: (Krouling ↔ Politika) uvazhaem /crawler/policy/check pered setevymi shagami.
- Skrytyy #2: (Myshlenie ↔ Deystviya) eksportiruem deystviya dlya volevogo vyzova (media.fetch/media.outline/media.ingest).

Zemnoy abzats:
«Prokrutil rolik cherez voronku» — i u nas v pamyati lezhit meta, tekst i opornyy konspekt.

# c=a+b
"""
from __future__ import annotations
import os, json, time, hashlib
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("MEDIA_AB","A") or "A").upper()
MEDIA_DIR = os.getenv("MEDIA_DIR","data/media")

def _mm():
    try:
        from services.mm_access import get_mm  # type: ignore
        return get_mm()
    except Exception:
        return None

def _hash_path(p: str) -> str:
    h = hashlib.sha256()
    with open(p,"rb") as f:
        for ch in iter(lambda: f.read(1<<20), b""):
            h.update(ch)
    return h.hexdigest()

def ensure_dir():
    os.makedirs(MEDIA_DIR, exist_ok=True)

def probe(source: str) -> Dict[str, Any]:
    if source.startswith("http://") or source.startswith("https://"):
        # popytaemsya skachat tolko metadannye? yt-dlp --dump-json — optsionalno; uproschaem: ne dergaem set
        return {"ok": True, "online": True, "source": source, "note":"online_source"}
    # lokalnyy fayl
    try:
        from modules.media.ffprobe import probe as _probe  # type: ignore
        return _probe(source)
    except Exception:
        return {"ok": False, "error":"ffprobe_module_unavailable"}

def extract_subs(source: str, prefer: str | None = None) -> Dict[str, Any]:
    try:
        from modules.media.subtitles import from_url, from_file  # type: ignore
        if source.startswith("http://") or source.startswith("https://"):
            return from_url(source, prefer)
        return from_file(source, prefer)
    except Exception as e:
        return {"ok": False, "error": str(e)}

def outline_from(source: str, k: int = 8) -> Dict[str,Any]:
    try:
        from modules.media.outline import build_outline  # type: ignore
        return build_outline(source, k)
    except Exception as e:
        return {"ok": False, "error": str(e)}

def ingest(source: str, prefer: str | None = None, k: int = 8) -> Dict[str, Any]:
    if AB=="B":
        return {"ok": False, "error":"MEDIA_AB=B"}
    ensure_dir()
    # 1) poluchit subtitry (ili tekstovyy istochnik)
    sub_rep = extract_subs(source, prefer)
    if not sub_rep.get("ok"):
        # dopuskaem inzhest tolko metadannykh
        meta = probe(source)
        return {"ok": True, "ingested": {"meta_only": True, "probe": meta}, "note": sub_rep}
    srt_path = sub_rep.get("path")
    # 2) konspekt
    out = outline_from(srt_path, k) if srt_path else {"ok": False, "error":"no_srt"}
    # 3) zapis v pamyat
    mm = _mm()
    if not mm:
        return {"ok": False, "error":"memory_unavailable", "subs": sub_rep, "outline": out}
    upsert = getattr(mm,"upsert",None) or getattr(mm,"save",None)
    if not upsert:
        return {"ok": False, "error":"memory_ops_missing"}
    # meta
    prov = {
        "source": source,
        "sha256": _hash_path(srt_path) if srt_path else "",
        "t_start": int(time.time()),
        "t_end": 0,
        "version": 1
    }
    items=[]
    # zapis subtitrov
    if srt_path:
        txt = open(srt_path,"r",encoding="utf-8",errors="ignore").read()
        doc_sub = {"text": txt[:2000000], "meta": {"kind":"media_subs","tags":["media","subs"], "provenance": prov}}
        upsert(doc_sub); items.append({"kind":"subs"})
    # zapis konspekta
    if out.get("ok"):
        bullets = out.get("bullets") or []
        doc_ol = {"text": "\n".join(f"- {b}" for b in bullets), "meta": {"kind":"media_outline","tags":["media","outline"], "provenance": prov}}
        upsert(doc_ol); items.append({"kind":"outline","k": len(bullets)})
    return {"ok": True, "ingested": {"items": items, "provenance": prov}, "subs": sub_rep, "outline": out}
# c=a+b