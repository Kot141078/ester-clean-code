# -*- coding: utf-8 -*-
"""
R2/services/ingest/rss_ingestor.py — prosteyshiy RSS/Atom parser i ingenst v CardsMemory.

Mosty:
- Yavnyy: Enderton — predmetnaya model (item) kak kortezh predikatov: title ∧ link ∧ summary ∧ ts.
- Skrytyy #1: Cover & Thomas — berem «signal» (zagolovok+annotatsiya), otbrasyvaem «shum» (HTML).
- Skrytyy #2: Ashbi — regulyator prost: tolko stdlib XML, bez vneshnikh lib; ne lomaet sistemu pri sboyakh.

Zemnoy abzats:
Chitaet RSS/Atom po URL (http(s) ili file://), vytaskivaet title/link/summary/updated, normalizuet,
i dobavlyaet kartochki v CardsMemory cherez mm_access.get_mm(). Dedup po sha256 teksta, zhurnal v data/ingest/rss_seen.json.

# c=a+b
"""
from __future__ import annotations
import json
import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

from services.mm_access import get_mm  # type: ignore
from services.ingest.normalizer import normalize_text, compute_hash  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SEEN_PATH = None  # lenivo initsializiruem posle PERSIST_DIR

def _persist_paths():
    global SEEN_PATH
    persist_dir = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    ingest_dir = os.path.join(persist_dir, "ingest")
    os.makedirs(ingest_dir, exist_ok=True)
    SEEN_PATH = os.path.join(ingest_dir, "rss_seen.json")
    if not os.path.isfile(SEEN_PATH):
        with open(SEEN_PATH, "w", encoding="utf-8") as f:
            json.dump({"seen": {}}, f)

def _read_url(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.read()

def _parse_rss_atom(xml_bytes: bytes) -> List[Dict[str, str]]:
    """
    Vozvraschaet spisok slovarey: {title, link, summary, updated}
    """
    items: List[Dict[str, str]] = []
    root = ET.fromstring(xml_bytes)

    # Atom?
    ns_atom = "{http://www.w3.org/2005/Atom}"
    ns_rss_content = "{http://purl.org/rss/1.0/modules/content/}"

    if root.tag.endswith("feed"):  # Atom
        for entry in root.findall(f".//{ns_atom}entry"):
            title = (entry.findtext(f"{ns_atom}title") or "").strip()
            link_node = entry.find(f"{ns_atom}link")
            link = (link_node.get("href") if link_node is not None else "") or ""
            summary = (entry.findtext(f"{ns_atom}summary") or entry.findtext(f"{ns_atom}content") or "").strip()
            updated = (entry.findtext(f"{ns_atom}updated") or "").strip()
            items.append({"title": title, "link": link, "summary": summary, "updated": updated})
        return items

    # RSS (2.0)
    for ch in root.findall(".//channel"):
        for it in ch.findall("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            summary = (it.findtext("description") or it.findtext(f"{ns_rss_content}encoded") or "").strip()
            updated = (it.findtext("pubDate") or "").strip()
            items.append({"title": title, "link": link, "summary": summary, "updated": updated})
    if items:
        return items

    # RSS 1.0
    for it in root.findall(".//item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        summary = (it.findtext("description") or "").strip()
        updated = ""
        items.append({"title": title, "link": link, "summary": summary, "updated": updated})

    return items

def ingest_rss(url: str, user: str = "Owner", tag: str = "rss") -> Dict[str, int]:
    """
    Zagruzhaet RSS/Atom, normalizuet i pishet kartochki.
    """
    _persist_paths()
    assert SEEN_PATH is not None
    try:
        raw = _read_url(url)
    except Exception as e:
        return {"ok": 0, "added": 0, "seen": 0, "errors": 1}

    items = _parse_rss_atom(raw)
    mm = get_mm()
    # zagruzit zhurnal
    seen = json.load(open(SEEN_PATH, "r", encoding="utf-8"))
    seen_map: Dict[str, float] = dict(seen.get("seen") or {})
    added = 0
    for it in items:
        base_text = f"{it.get('title','').strip()}\n{it.get('link','').strip()}\n\n{it.get('summary','').strip()}"
        txt, _mime = normalize_text(base_text.encode("utf-8"), name="rss.txt")
        h = compute_hash(txt)
        if h in seen_map:
            continue
        # dobavit kartochku
        try:
            mm.cards.add_card(user, text=txt, tags=[tag], weight=0.5)  # type: ignore[attr-defined]
            added += 1
            seen_map[h] = time.time()
        except Exception:
            # ne preryvaem tsikl
            continue

    # sokhranit zhurnal
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump({"seen": seen_map}, f, ensure_ascii=False, indent=2)
    return {"ok": 1, "added": added, "seen": len(seen_map), "errors": 0}