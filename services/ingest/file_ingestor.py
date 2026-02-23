# -*- coding: utf-8 -*-
"""
R2/services/ingest/file_ingestor.py — skaner lokalnoy papki i ingenst tekstov.

Mosty:
- Yavnyy: Enderton — invarianty: fayl→normalizatsiya→dedup→kartochka (chetkie predikaty na kazhdom shage).
- Skrytyy #1: Ashbi — prostaya regulyatsiya nagruzki: posledovatelnaya obrabotka, bez fonovykh demonov.
- Skrytyy #2: Cover & Thomas — minimalnyy «signal» (tekst) dlya popolneniya pamyati, bez lishnego shuma (binarniki ignorim).

Zemnoy abzats:
Rekursivno obkhodit `INBOX_DIR` (ili peredannyy put), parsit .txt/.md/.html, normalizuet,
kladet v CardsMemory, khranit dedup-kheshi v `data/ingest/inbox_seen.json`. Bez vneshnikh zavisimostey.

# c=a+b
"""
from __future__ import annotations
import fnmatch
import json
import os
from typing import Dict, List

from services.mm_access import get_mm  # type: ignore
from services.ingest.normalizer import normalize_text, compute_hash  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SEEN_PATH = None

def _persist_paths():
    global SEEN_PATH
    persist_dir = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    ingest_dir = os.path.join(persist_dir, "ingest")
    os.makedirs(ingest_dir, exist_ok=True)
    SEEN_PATH = os.path.join(ingest_dir, "inbox_seen.json")
    if not os.path.isfile(SEEN_PATH):
        with open(SEEN_PATH, "w", encoding="utf-8") as f:
            json.dump({"seen": {}}, f)

def inbox_scan(root: str | None = None, user: str = "Owner", tag: str = "inbox", pattern: str = "*.txt;*.md;*.markdown;*.html;*.htm") -> Dict[str, int]:
    _persist_paths()
    assert SEEN_PATH is not None
    root = root or os.getenv("INBOX_DIR") or os.path.abspath(os.path.join(os.getcwd(), "inbox"))
    patts = [p.strip() for p in (pattern or "").split(";") if p.strip()]
    mm = get_mm()

    seen = json.load(open(SEEN_PATH, "r", encoding="utf-8"))
    seen_map: Dict[str, float] = dict(seen.get("seen") or {})
    added, skipped = 0, 0

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if not any(fnmatch.fnmatch(fn.lower(), p.lower()) for p in patts):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, "rb") as f:
                    raw = f.read()
                txt, mime = normalize_text(raw, name=fn)
                if not txt.strip():
                    skipped += 1
                    continue
                h = compute_hash(txt)
                if h in seen_map:
                    skipped += 1
                    continue
                mm.cards.add_card(user, text=txt, tags=[tag], weight=0.5)  # type: ignore[attr-defined]
                seen_map[h] = float(os.path.getmtime(path))
                added += 1
            except Exception:
                skipped += 1
                continue

    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump({"seen": seen_map}, f, ensure_ascii=False, indent=2)
    return {"ok": 1, "added": added, "skipped": skipped, "seen": len(seen_map)}