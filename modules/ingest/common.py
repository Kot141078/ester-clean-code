# -*- coding: utf-8 -*-
"""
modules.ingest.common — obschie khelpery dlya ingest/ocr/pdf i pr.

MOSTY:
- (Yavnyy) persist_dir/save_bytes/pdf_text_extract/sha256_file ↔ routes.ingest_* i dreams_routes.
- (Skrytyy #1) KG ↔ ingest: kg_attach_artifact/add_structured_record vyzyvayut KGStore, esli dostupen.
- (Skrytyy #2) Memory ↔ ENV: build_mm_from_env vozvraschaet obekt pamyati, opirayas na PERSIST_DIR.

ZEMNOY ABZATs:
Praktichnye funktsii, kotorye mozhno zvat iz routov bez tyazhelykh zavisimostey (OCR/psutil/cryptography ne obyazatelny).
# c=a+b
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import fitz  # PyMuPDF (optsionalno)
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

# ---- faylovye primitivy ----
def persist_dir() -> str:
    root = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(root, exist_ok=True)
    return root

def save_bytes(path: str, data: bytes) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def sniff_mime(path: str) -> str:
    low = path.lower()
    if low.endswith(".pdf"): return "application/pdf"
    if low.endswith(".png"): return "image/png"
    if low.endswith(".jpg") or low.endswith(".jpeg"): return "image/jpeg"
    if low.endswith(".txt") or low.endswith(".md"): return "text/plain"
    return "application/octet-stream"

# ---- PDF (myagko) ----
def pdf_text_extract(pdf_bytes: bytes) -> str:
    if not fitz:
        # Folbek: poprobuem «na glaz» — inogda PDF soderzhit tekst kak utf-8
        try:
            txt = pdf_bytes.decode("utf-8")
            return txt if len(txt.strip()) > 0 else ""
        except Exception:
            return ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        parts = []
        for p in doc:
            parts.append(p.get_text())
        return "\n".join(parts)
    except Exception:
        return ""

# ---- Memory/KG (myagko) ----
def add_structured_record(text: str, tags: Iterable[str] = ()) -> str:
    rid = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    try:
        from memory.kg_store import KGStore  # type: ignore
        KGStore().add_record(rid, {"text": text, "tags": list(tags)})
    except Exception:
        pass
    return rid

def kg_attach_artifact(label: str, text: str, tags: Iterable[str] = ()) -> None:
    try:
        from memory.kg_store import KGStore  # type: ignore
        KGStore().add_edge({"label": label, "payload": {"text": text, "tags": list(tags)}})
    except Exception:
        pass

# ---- Mini-pamyat iz ENV ----
@dataclass
class MiniMemory:
    base: str

    def put(self, key: str, payload: Dict[str, Any]) -> str:
        p = Path(self.base) / "memory" / f"{key}.json"
        os.makedirs(p.parent, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return str(p)

def build_mm_from_env() -> MiniMemory:
    """Vozvraschaet legkiy obekt pamyati, zavyazannyy na PERSIST_DIR."""
    return MiniMemory(base=persist_dir())