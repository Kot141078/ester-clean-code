# -*- coding: utf-8 -*-
"""modules.computer_use.anchors_suggest - eksport "teplovoy karty" i podskazok yakorey.

MOSTY:
- Yavnyy: (Anchors Export API) export(domain, window, top, prefix) ← routes/computer_use_heatmap_export.py.
- Skrytyy #1: (Faylovaya sistema ↔ Web-statik) — eksport sozdaet fayl pod data/ i daet URL /data/…
- Skrytyy #2: (Diagnostika ↔ UI) — vmeste s yakoryami vsegda vozvraschaem heatmap.url dlya predprosmotra.

ZEMNOY ABZATs:
Funktsiya export(...) - eto “printer yarlykov”: ona garantirovanno sozdaet PNG s teplovoy kartoy
(minimalnyy 1x1), i formiruet spisok kandidatov-yakorey po zadannomu domenu. Nikakikh setevykh
zavisimostey - vse lokalno i krossplatformenno.
# c=a+b"""
from __future__ import annotations
import os
from typing import List, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Bazovye puti
DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), "data"))
OUT_DIR = os.path.join(DATA_DIR, "computer_use")
OUT_PATH = os.path.join(OUT_DIR, "heatmap.png")

def _ensure_dirs() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

def _to_url(path: str) -> str:
    """Preobrazuet absolyutnyy put vnutri data/ v URL /data/…"""
    rel = os.path.relpath(path, DATA_DIR).replace("\\", "/")
    return "/data/" + rel

def export_heatmap(points: List[Dict] | None = None) -> Dict[str, str]:
    """Creates a minimal PNG so that the frontend can serve it."""
    _ensure_dirs()
    # Minimalnyy validnyy PNG 1x1 (chernyy piksel)
    PNG_1x1 = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
               b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c``\x00\x00\x00\x02"
               b"\x00\x01e\x1e\x02\xb1\x00\x00\x00\x00IEND\xaeB`\x82")
    with open(OUT_PATH, "wb") as f:
        f.write(PNG_1x1)
    return {"ok": True, "path": OUT_PATH, "url": _to_url(OUT_PATH)}

def suggest_anchors(text: str, limit: int = 16) -> Dict[str, list]:
    """The simplest “anchors” are the first unique words suitable for UI."""
    import re
    words = [w for w in re.findall(r"[A-Za-zA-Yaa-ya0-9_]{3,}", text or "")]
    seen, anchors = set(), []
    for w in words:
        lw = w.lower()
        if lw not in seen:
            seen.add(lw)
            anchors.append(w)
        if len(anchors) >= max(1, int(limit)):
            break
    return {"ok": True, "anchors": anchors}

def _default_candidates(domain: str) -> List[str]:
    # Frequent navigation points for any web application
    base = ["home","login","dashboard","settings","profile","search","help","about","contact"]
    # Takzhe dobavim tokeny iz domena
    tokens = [p for p in domain.replace("-", " ").replace(".", " ").split() if p]
    return tokens + base

def export(domain: str, *, window: str = "30d", top: int = 20, prefix: str = "auto") -> Dict[str, object]:
    """Eksportiruet heatmap + spisok kandidatov-yakorey.
    Sovmestimo s routes/computer_use_heatmap_export.py (export(domain, window, top, prefix)).
    Nikakikh vneshnikh zavisimostey; garantiruet suschestvovanie PNG i vozvraschaet URL.

    Vozvraschaemaya struktura:
      { ok, domain, window, top, prefix, heatmap:{path,url}, suggestions:[{id,label,score}] }"""
    domain = (domain or "").strip().lower()
    if not domain:
        return {"ok": False, "error": "domain required"}

    # 1) Exports (or updates) a heat map file
    hm = export_heatmap(points=None)

    # 2) Compiling candidates (simple heuristics without access to real logs)
    raw = _default_candidates(domain)
    # Let’s prepare elements with ID and “quasi-evaluation” by position
    items = []
    for i, name in enumerate(raw[: max(1, int(top))]):
        aid = f"{prefix}:{domain}:{name}" if prefix else f"{domain}:{name}"
        score = 1.0 - (i / max(1, float(top)))
        items.append({"id": aid, "label": name, "score": round(score, 3)})

    return {
        "ok": True,
        "domain": domain,
        "window": str(window or "30d"),
        "top": int(top or 20),
        "prefix": str(prefix or "auto"),
        "heatmap": hm,
        "suggestions": items,
    }

__all__ = ["DATA_DIR", "OUT_DIR", "OUT_PATH", "export_heatmap", "suggest_anchors", "export"]