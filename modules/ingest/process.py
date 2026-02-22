# -*- coding: utf-8 -*-
"""
modules/ingest/process.py — unified ingest pipeline (file/bytes/text) with fallback.

Pipeline:
read -> chunk -> vstore upsert -> doc_summary (structured) -> links

AB:
  ESTER_INGEST_PIPELINE_AB=A (default) -> .pdf/.txt/.md only
  ESTER_INGEST_PIPELINE_AB=B -> + .docx/.doc/.html/.htm

Ext gates:
  A: .pdf/.txt/.md
  B: + .docx/.doc/.html/.htm
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from modules.memory.facade import memory_add

try:
    import file_readers as _fr  # type: ignore
except Exception:
    _fr = None  # type: ignore

try:
    from chunking import chunk_document  # type: ignore
except Exception:
    chunk_document = None  # type: ignore


AB = (os.getenv("ESTER_INGEST_PIPELINE_AB", "A") or "A").upper()
ALLOW_A = {".pdf", ".txt", ".md"}
ALLOW_B = ALLOW_A | {".docx", ".doc", ".html", ".htm"}


def _now() -> float:
    return time.time()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b or b"").hexdigest()


def _detect_lang(text: str) -> str:
    if not text:
        return "unknown"
    # kirillitsa → ru, inache en
    for ch in text:
        if "A" <= ch <= "ya" or ch in ("E", "e"):
            return "ru"
    return "en"


def _sniff_mime(ext: str) -> str:
    ext = (ext or "").lower()
    if ext == ".pdf":
        return "application/pdf"
    if ext in (".txt", ".md"):
        return "text/plain"
    if ext in (".html", ".htm"):
        return "text/html"
    if ext in (".docx", ".doc"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return "application/octet-stream"


def _ext_allowed(ext: str) -> bool:
    ext = (ext or "").lower()
    if AB == "B":
        return ext in ALLOW_B
    return ext in ALLOW_A


def _read_raw(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _normalize_detect_and_read(name: str, raw: bytes) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
    # Prefer file_readers.detect_and_read if available; normalize output
    if _fr is not None and hasattr(_fr, "detect_and_read"):
        try:
            res = _fr.detect_and_read(name, raw)  # type: ignore[attr-defined]
            if isinstance(res, tuple) and len(res) == 3:
                sections, full_text, head = res
                return sections or [], (full_text or ""), (head or {})
            if isinstance(res, tuple) and len(res) == 2:
                sections, full_text = res
                head = {}
                return sections or [], (full_text or ""), head
        except Exception:
            pass

    # Fallback: decode as text
    text = ""
    for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1251", "latin-1"):
        try:
            text = (raw or b"").decode(enc)
            break
        except Exception:
            continue
    if not text:
        text = (raw or b"").decode("utf-8", errors="replace")
    sections = [{"kind": "text", "title": name, "index": 0, "text": text}]
    head = {"title": name, "ext": os.path.splitext(name)[1].lower(), "mime": _sniff_mime(os.path.splitext(name)[1].lower()), "lang": _detect_lang(text)}
    return sections, text, head


def _ensure_head(head: Dict[str, Any], name: str, ext: str, text: str) -> Dict[str, Any]:
    h = dict(head or {})
    h.setdefault("title", name or "document")
    h.setdefault("ext", ext)
    h.setdefault("mime", _sniff_mime(ext))
    h.setdefault("lang", _detect_lang(text))
    return h


def _vstore() -> Any:
    try:
        from vector_store import VectorStore  # type: ignore
        return VectorStore(
            collection_name=os.getenv("COLLECTION_NAME", "ester_store"),
            persist_dir=os.getenv("PERSIST_DIR", ""),
            use_embeddings=bool(int(os.getenv("USE_EMBEDDINGS", "0"))),
        )
    except Exception:
        return None


def _vstore_upsert(vstore: Any, texts: List[str], ids: List[str], metas: List[Dict[str, Any]]) -> None:
    if not vstore or not texts:
        return
    if hasattr(vstore, "upsert_texts"):
        for i in range(len(texts)):
            vstore.upsert_texts([texts[i]], ids=[ids[i]], meta=metas[i])
        return
    if hasattr(vstore, "add_texts"):
        for i in range(len(texts)):
            vstore.add_texts([texts[i]], meta=metas[i])
        return
    raise AttributeError("vstore must provide upsert_texts() or add_texts()")


def _autolink(doc_id: str, text: str) -> None:
    if not doc_id or not text:
        return
    try:
        from modules.kg.autolink import autolink  # type: ignore
        autolink([{"id": doc_id, "text": text, "tags": ["doc"], "meta": {"doc_id": doc_id}}], mode="simple", link_to_rag=True)
    except Exception:
        pass


def _legacy_cards_ingest(text: str, title: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        from cards_memory import CardsMemory  # type: ignore
        from memory_manager import MemoryManager  # type: ignore
        from structured_memory import StructuredMemory  # type: ignore
        from vector_store import VectorStore  # type: ignore

        persist_dir = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
        os.makedirs(persist_dir, exist_ok=True)

        vstore = VectorStore(
            collection_name=os.getenv("COLLECTION_NAME", "ester_store"),
            persist_dir=persist_dir,
            use_embeddings=bool(int(os.getenv("USE_EMBEDDINGS", "0"))),
        )
        structured = StructuredMemory(os.path.join(persist_dir, "structured_mem", "store.json"))  # type: ignore
        cards = CardsMemory(os.path.join(persist_dir, "ester_cards.json"))  # type: ignore
        mm = MemoryManager(vstore, structured, cards)  # type: ignore

        tags = ["ingest"]
        rid = mm.structured.add_record(text=text, tags=tags, weight=0.5)  # type: ignore[attr-defined]
        try:
            mm.cards.add_card(header=title, body=text[:600], tags=tags)  # type: ignore[attr-defined]
        except Exception:
            pass
        return {"ok": True, "legacy": True, "record_id": rid}
    except Exception as e:
        return {"ok": False, "legacy": True, "error": str(e)}


def ingest_process_bytes(
    name: str,
    raw: bytes,
    *,
    source: str = "ingest",
    meta: Optional[Dict[str, Any]] = None,
    source_path: str = "",
) -> Dict[str, Any]:
    meta = dict(meta or {})
    ext = os.path.splitext(name or "")[1].lower()
    if not _ext_allowed(ext):
        return {"ok": False, "skipped": True, "reason": "ext_not_allowed", "ext": ext}

    try:
        doc_id = _sha256_bytes(raw)
        sections, full_text, head = _normalize_detect_and_read(name, raw)
        if sections and not full_text:
            full_text = "\n\n".join([s.get("text", "") for s in sections if isinstance(s, dict)])
        if not (full_text or "").strip():
            return {"ok": False, "reason": "empty_text"}

        head = _ensure_head(head, name or "document", ext, full_text)

        if chunk_document is None:
            legacy = _legacy_cards_ingest(full_text, name or "document", meta=meta)
            legacy["fallback"] = True
            legacy["error"] = "chunking_unavailable"
            return legacy

        chunks = chunk_document(doc_id, sections if sections else [{"text": full_text}], head)  # type: ignore
        chunks = [c for c in (chunks or []) if isinstance(c, dict) and (c.get("text") or "").strip()]

        # vstore
        vstore = _vstore()
        texts: List[str] = []
        ids: List[str] = []
        metas: List[Dict[str, Any]] = []
        for i, ch in enumerate(chunks):
            texts.append(str(ch.get("text") or ""))
            ids.append(f"{doc_id}:{i}")
            cm = dict(ch.get("meta") or {})
            cm.update({
                "doc_id": doc_id,
                "source": source,
                "source_path": source_path or name,
                "chunk_index": i,
                "ext": ext,
                "title": head.get("title"),
                "ingested_ts": _now(),
            })
            metas.append(cm)
        _vstore_upsert(vstore, texts, ids, metas)

        # doc object + summary
        try:
            from modules.memory.doc_store import ingest_document  # type: ignore
            ingest_document(
                raw=raw,
                orig_name=name,
                full_text=full_text,
                chunks=chunks,
                source_path=source_path or name,
                meta={"source": source, **meta},
            )
        except Exception:
            pass

        # links (KG autolink)
        try:
            summary = " ".join((full_text or "").split())[:1200]
        except Exception:
            summary = ""
        _autolink(doc_id, summary or full_text[:2000])

        return {"ok": True, "doc_id": doc_id, "chunks": len(chunks), "full_text": full_text, "head": head}

    except Exception as e:
        # auto-rollback
        try:
            text = (raw or b"").decode("utf-8", errors="replace")
        except Exception:
            text = ""
        legacy = _legacy_cards_ingest(text, name or "document", meta=meta)
        legacy["fallback"] = True
        legacy["error"] = str(e)
        return legacy


def ingest_process_file(path: str, *, source: str = "folder", meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not path:
        return {"ok": False, "reason": "empty_path"}

    # Queue envelope support: JSON with path/content_b64/meta
    if path.lower().endswith(".json") and os.path.isfile(path):
        try:
            data = json.loads(open(path, "r", encoding="utf-8").read())
            if isinstance(data, dict) and data.get("path"):
                inner_path = str(data.get("path"))
                meta = dict(meta or {})
                meta.update(data.get("meta") or {})
                return ingest_process_file(inner_path, source=source, meta=meta)
            if isinstance(data, dict) and data.get("content_b64"):
                raw = base64.b64decode(data.get("content_b64") or "")
                name = data.get("name") or data.get("filename") or "payload.bin"
                meta = dict(meta or {})
                meta.update(data.get("meta") or {})
                return ingest_process_bytes(str(name), raw, source=source, meta=meta, source_path=path)
        except Exception:
            pass

    if not os.path.isfile(path):
        return {"ok": False, "reason": "file_not_found", "path": path}

    ext = os.path.splitext(path)[1].lower()
    if not _ext_allowed(ext):
        return {"ok": False, "skipped": True, "reason": "ext_not_allowed", "ext": ext}

    try:
        raw = _read_raw(path)
        name = os.path.basename(path) or path
        return ingest_process_bytes(name, raw, source=source, meta=meta, source_path=path)
    except Exception as e:
        return {"ok": False, "reason": f"read_error:{e}"}


__all__ = ["ingest_process_file", "ingest_process_bytes"]
