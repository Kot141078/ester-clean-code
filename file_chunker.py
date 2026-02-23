# -*- coding: utf-8 -*-
from __future__ import annotations

"""file_chunker.py — chankovanie vkhodnykh faylov dlya ingest (samodostatochno, best-effort).

Problemy iskhodnika:
- Krakozyabry v dokstringe (slomannaya perekodirovka).
- chunk_file() inogda vozvraschal None (fallback return byl zakommentirovan i dazhe vylez iz bloka).
- _split() mog uyti v beskonechnyy tsikl, esli razdelitel nayden rovno v pozitsii i.
- Chtenie teksta delalos errors='ignore' → tikho teryalis simvoly.

Chto sdelano:
- Chtenie teksta: probuem utf-8/utf-16/cp1251/latin-1 (errors='replace'), bez “tishiny”.
- PDF: pypdf → PyPDF2 → binarnyy fallback.
- Dobavlen overlap (perekrytie), chtoby kontekst ne “rubilsya” na granitsakh.
- Razrez po granitsam: \n\n / \n / '. ' / ' ' — s garantiey progressa.
- API sovmestim: chunk_file(path) -> List[str]. Plyus chunk_text(text) i ChunkerConfig.

Mosty (trebovanie):
- Yavnyy most: ingest-payplayn (fayl→chanki) ↔ pamyat/vektorizatsiya (chanki kak atomy khraneniya).
- Skrytye mosty:
  1) Infoteoriya ↔ ekspluatatsiya: limit+overlap = kontrol propusknoy sposobnosti kanala + zaschita ot poteri “smysla na styke”.
  2) Inzheneriya ↔ nadezhnost: best-effort chtenie formatov (pdf/docx/html) → degradatsiya vmesto padeniya.

ZEMNOY ABZATs: v kontse fayla.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_WS_RE = re.compile(r"[\t\r ]+")
_NL3_RE = re.compile(r"\n{3,}")
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class ChunkerConfig:
    limit: int = 1500          # tselevoy razmer chanka v simvolakh
    overlap: int = 150         # perekrytie mezhdu chankami (simvoly)
    max_chars: int = 400_000   # zaschitnyy limit na vkhodnoy tekst
    keep_empty: bool = False   # sokhranyat li pustye chanki


def _clean_text(text: str) -> str:
    t = (text or "").replace("\ufeff", "")
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _WS_RE.sub(" ", t)
    t = _NL3_RE.sub("\n\n", t)
    return t.strip()


def _read_text_best_effort(path: str) -> str:
    p = Path(path)
    data = p.read_bytes()
    # poryadok: chastoe → redkoe
    for enc in ("utf-8", "utf-16", "cp1251", "latin-1"):
        try:
            return data.decode(enc, errors="replace")
        except Exception:
            continue
    return data.decode("latin-1", errors="replace")


def _read_pdf_best_effort(path: str) -> str:
    p = Path(path)
    # 1) pypdf (sovremennee)
    try:
        from pypdf import PdfReader  # type: ignore
        r = PdfReader(str(p))
        parts: List[str] = []
        for pg in r.pages:
            try:
                parts.append(pg.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts)
    except Exception:
        pass

    # 2) PyPDF2 (esli staroe)
    try:
        import PyPDF2  # type: ignore
        parts2: List[str] = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for pg in reader.pages:
                try:
                    parts2.append(pg.extract_text() or "")
                except Exception:
                    continue
        return "\n".join(parts2)
    except Exception:
        pass

    # 3) fallback
    return p.read_bytes().decode("latin-1", errors="replace")


def _read_docx_best_effort(path: str) -> str:
    try:
        import docx  # type: ignore
    except Exception:
        return ""
    try:
        d = docx.Document(path)
        return "\n".join([para.text for para in d.paragraphs if para.text])
    except Exception:
        return ""


def _read_html_best_effort(path: str) -> str:
    raw = _read_text_best_effort(path)
    # grubo ubrat tegi
    raw = _TAG_RE.sub(" ", raw)
    return raw


def _find_cut(text: str, start: int, end: int) -> int:
    """Ischem luchshuyu tochku razreza v [start, end], garantiruya progress."""
    if end <= start:
        return start

    # prioritet: dvoynoy perevod stroki → odinarnyy → '. ' → probel
    candidates = []
    for pat in ("\n\n", "\n", ". ", " "):
        idx = text.rfind(pat, start, end)
        if idx != -1:
            # razrezaem POSLE razdelitelya
            cut = idx + len(pat)
            candidates.append(cut)

    cut = candidates[0] if candidates else end
    # garantiya progressa: esli cut ne dvigaet — rezhem po end
    if cut <= start:
        cut = end
    return cut


def chunk_text(text: str, cfg: Optional[ChunkerConfig] = None) -> List[str]:
    cfg = cfg or ChunkerConfig()
    limit = max(200, int(cfg.limit))
    overlap = max(0, int(cfg.overlap))
    max_chars = max(10_000, int(cfg.max_chars))

    t = _clean_text(text)
    if not t:
        return [] if not cfg.keep_empty else [""]

    if len(t) > max_chars:
        t = t[:max_chars]

    out: List[str] = []
    i = 0
    n = len(t)

    while i < n:
        j = min(i + limit, n)
        cut = _find_cut(t, i, j)
        chunk = t[i:cut].strip()
        if chunk or cfg.keep_empty:
            out.append(chunk)

        if cut >= n:
            break

        # overlap: shag nazad, no ne bolshe tekuschego chanka
        if overlap > 0:
            i = max(0, cut - overlap)
            # zaschita ot zalipaniya: esli overlap slishkom bolshoy
            if i >= cut:
                i = cut
        else:
            i = cut

        # esche odna zaschita: esli po kakoy-to prichine ne prodvinulis
        if out and (len(out) > 1) and (i <= 0 and cut <= 0):
            break

    return [x for x in out if x] if not cfg.keep_empty else out


def _read_by_ext(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in (".txt", ".md", ".markdown", ".csv", ".log", ".json", ".yaml", ".yml", ".py"):
        return _read_text_best_effort(path)
    if ext == ".pdf":
        return _read_pdf_best_effort(path)
    if ext == ".docx":
        return _read_docx_best_effort(path)
    if ext in (".html", ".htm"):
        return _read_html_best_effort(path)
    # unknown — popytatsya kak tekst
    try:
        return _read_text_best_effort(path)
    except Exception:
        return Path(path).read_bytes().decode("latin-1", errors="replace")


def chunk_file(path: str, limit: int = 1500) -> List[str]:
    """Sovmestimyy API: kak ranshe, no nadezhnee."""
    cfg = ChunkerConfig(limit=int(limit))
    raw = _read_by_ext(path)
    return chunk_text(raw, cfg=cfg)


__all__ = ["ChunkerConfig", "chunk_text", "chunk_file"]


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Chankovanie — eto “perezhevyvanie”: esli otkusit slishkom bolshoy kusok — podavishsya (model/pamyat),
esli slishkom malenkiy — teryaesh vkus i kontekst. Overlap — kak slyuna i poslevkusie: chut-chut perenosim
smysl cherez granitsu, chtoby ne rvat mysl na rovnom meste.
"""