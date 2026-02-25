# -*- coding: utf-8 -*-
from __future__ import annotations

"""file_ingest.py - minimalnyy ingest bez vneshnikh zavisimostey.

Zachem:
- Nekotorye moduli ozhidayut `from file_ingest import ingest_file`.
- V proekte est `services/ingest/file_ingestor.py`, no eto drugoy modul i s dependent.
- Etot shim delaet sistemu samodostatochnoy: tekstovye fayly chitayutsya i rezhutsya na chanki.

Podderzhka (best-effort):
- .txt/.md/.markdown/.log/.json/.yaml/.yml/.py/.csv
- .html/.htm (gruboe udalenie tegov)
- .pdf (if ustanovlen pypdf)
- .docx (if ustanovlen python-docx)

API:
- ingest_file(path, chunk_size=1200, max_chars=200_000) -> list[str]
- ingest_text(text, chunk_size=1200, max_chars=200_000) -> list[str]

Mosty:
- Yavnyy: fayl → normalizatsiya → chanki → dalshe v pamyat/vektorizatsiyu.
- Skrytye:
  1) Infoteoriya ↔ shumoustoychivost: max_chars ogranichivaet kanal, ne daet “zalit” pamyat musorom.
  2) Inzheneriya ↔ ekspluatatsiya: best-effort dlya pdf/docx - modul ne padaet, a degradiruet.

ZEMNOY ABZATs: v kontse fayla."""

import os
import re
from pathlib import Path
from typing import List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[\t\r ]+")
_NL3_RE = re.compile(r"\n{3,}")


def _clean_text(t: str) -> str:
    t = (t or "").replace("\ufeff", "")
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _WS_RE.sub(" ", t)
    t = _NL3_RE.sub("\n\n", t)
    return t.strip()


def _chunk(text: str, chunk_size: int) -> List[str]:
    text = _clean_text(text)
    if not text:
        return []
    if chunk_size < 200:
        chunk_size = 200
    out: List[str] = []
    buf: List[str] = []
    n = 0
    for line in text.splitlines():
        ln = line.strip()
        if not ln:
            continue
        if n + len(ln) + 1 > chunk_size and buf:
            out.append("\n".join(buf))
            buf, n = [], 0
        buf.append(ln)
        n += len(ln) + 1
    if buf:
        out.append("\n".join(buf))
    return out


def ingest_text(text: str, chunk_size: int = 1200, max_chars: int = 200_000) -> List[str]:
    text = (text or "")
    if max_chars and len(text) > int(max_chars):
        text = text[: int(max_chars)]
    return _chunk(text, int(chunk_size))


def _read_pdf(p: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return ""
    try:
        r = PdfReader(str(p))
        parts = []
        for pg in r.pages:
            try:
                parts.append(pg.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts)
    except Exception:
        return ""


def _read_docx(p: Path) -> str:
    try:
        import docx  # type: ignore
    except Exception:
        return ""
    try:
        d = docx.Document(str(p))
        return "\n".join([para.text for para in d.paragraphs if para.text])
    except Exception:
        return ""


def ingest_file(path: str, chunk_size: int = 1200, max_chars: int = 200_000) -> List[str]:
    p = Path(path)
    if not p.exists():
        return []
    ext = p.suffix.lower().lstrip(".")
    raw = ""

    if ext in ("txt", "md", "markdown", "log", "json", "yaml", "yml", "py", "csv"):
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            try:
                raw = p.read_text(encoding="cp1251", errors="replace")
            except Exception:
                raw = ""

    elif ext in ("html", "htm"):
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            raw = ""
        raw = _TAG_RE.sub(" ", raw)

    elif ext in ("pdf",):
        raw = _read_pdf(p)

    elif ext in ("docx",):
        raw = _read_docx(p)

    else:
        # unknown format - try as text
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            raw = ""

    if max_chars and len(raw) > int(max_chars):
        raw = raw[: int(max_chars)]
    return _chunk(raw, int(chunk_size))


__all__ = ["ingest_file", "ingest_text"]


ZEMNOY = """ZEMNOY ABZATs (anatomiya/inzheneriya):
Ingest - eto kak pervichnyy osmotr patsienta: my ne delaem MRT kazhdoy bumazhke, no snimaem osnovnye pokazateli,
chtoby dalshe mozhno bylo lechit/analizirovat. Glavnoe - ne dopustit “peredozirovki” vkhodom: poetomu max_chars i chanki."""