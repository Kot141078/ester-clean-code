# -*- coding: utf-8 -*-
"""
R2/services/ingest/normalizer.py — normalizatsiya teksta iz RSS/faylov/HTML.

Mosty:
- Yavnyy: Dzheynes — normalizovannyy tekst eto «dokazatelstvo» dlya MM; povyshaem pravdopodobie poleznoy pamyati.
- Skrytyy #1: Enderton — determinirovannye preobrazovaniya (predikaty na mime/rasshirenii) ⇒ predskazuemyy rezultat.
- Skrytyy #2: Ashbi — A/B-slot: R2_MODE=A (minimum pravil), B (bolshe evristik); pri oshibke — avtokatbek na A.

Zemnoy abzats:
Izvlekaet tekst: dlya .txt/.md — pryamoy; dlya .html — udalyaem tegi; dlya «neizvestnykh» — kak est.
Minimalnaya deduplikatsiya po sha256 normalizovannogo teksta. Tolko stdlib.

# c=a+b
"""
from __future__ import annotations
import hashlib
import html
import os
import re
from html.parser import HTMLParser
from typing import Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._buf: list[str] = []
    def handle_data(self, d: str) -> None:
        self._buf.append(d)
    def get(self) -> str:
        return "".join(self._buf)

def strip_tags(html_text: str) -> str:
    p = _HTMLStripper()
    p.feed(html_text)
    return html.unescape(p.get())

_MD_RE = re.compile(r"(^|\s)[#*_>`~]{1,3}\s*|!\[[^\]]*\]\([^)]+\)|\[[^\]]+\]\([^)]+\)", re.M)

def normalize_text(raw: bytes, name: str) -> Tuple[str, str]:
    """
    Vozvraschaet (text, mime_hint). Oshibki ne brosaem — vsegda chto-to vernem.
    """
    mode = (os.getenv("R2_MODE") or "A").strip().upper()
    ext = os.path.splitext(name)[1].lower()
    try:
        s = raw.decode("utf-8", errors="replace")
        if ext in (".txt", ""):
            txt = s
            mime = "text/plain"
        elif ext in (".md", ".markdown"):
            txt = _MD_RE.sub(" ", s)
            mime = "text/markdown"
        elif ext in (".html", ".htm", ".xhtml", ".xml"):
            # A: gruboe snyatie tegov; B: plyus skhlopyvanie probelov
            core = strip_tags(s)
            txt = re.sub(r"\s{2,}", " ", core).strip() if mode == "B" else core
            mime = "text/html"
        else:
            # neizvestnoe — ostavlyaem kak est
            txt = s
            mime = "application/octet-stream"
        if mode == "B":
            # Legkaya normalizatsiya probelov/perevodov
            txt = re.sub(r"[ \t]+", " ", txt)
            txt = re.sub(r"\n{3,}", "\n\n", txt)
        return txt.strip(), mime
    except Exception:
        # Avtokatbek: vozvraschaem «kak est» (A-rezhim)
        return raw.decode("utf-8", errors="replace"), "application/octet-stream"