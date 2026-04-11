# -*- coding: utf-8 -*-
"""
Document Store (CAS): first-class document objects.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from modules.memory.facade import memory_add


_CACHE_LOCK = threading.RLock()
_INDEX_CACHE: Dict[str, Any] = {"stamp": None, "records": [], "by_doc_id": {}}
_META_CACHE: Dict[str, Dict[str, Any]] = {}
_NAME_CACHE: Dict[str, Any] = {"stamp": None, "entries": []}
_SEARCH_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]+", re.UNICODE)
_SEARCH_STOP_TOKENS = {
    "a",
    "an",
    "and",
    "doc",
    "docs",
    "document",
    "file",
    "html",
    "md",
    "of",
    "pdf",
    "readme",
    "report",
    "spec",
    "txt",
    "в",
    "во",
    "документ",
    "документы",
    "из",
    "на",
    "о",
    "об",
    "по",
    "про",
    "файл",
}


def _state_root() -> str:
    root = (os.environ.get("ESTER_STATE_DIR") or os.environ.get("ESTER_HOME") or os.environ.get("ESTER_ROOT") or os.getcwd()).strip()
    return root


def _docs_root() -> str:
    return os.path.join(_state_root(), "data", "memory", "docs")


def _meta_path(doc_id: str) -> str:
    return os.path.join(_docs_root(), "meta", f"{doc_id}.json")


def _summary_path(doc_id: str) -> str:
    return os.path.join(_docs_root(), "summary", f"{doc_id}.txt")


def _chunks_path(doc_id: str) -> str:
    return os.path.join(_docs_root(), "chunks", f"{doc_id}.jsonl")


def _citations_path(doc_id: str) -> str:
    return os.path.join(_docs_root(), "citations", f"{doc_id}.json")


def _search_path(doc_id: str) -> str:
    return os.path.join(_docs_root(), "search", f"{doc_id}.txt")


def _ensure_dirs() -> None:
    for p in ("raw", "meta", "chunks", "summary", "citations", "search"):
        os.makedirs(os.path.join(_docs_root(), p), exist_ok=True)


def _doc_id(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _index_path() -> str:
    return os.path.join(_docs_root(), "index.jsonl")


def _path_stamp(path: str) -> Tuple[bool, int, int]:
    try:
        st = os.stat(path)
        return True, int(st.st_size), int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
    except Exception:
        return False, 0, 0


def _index_stamp() -> Tuple[bool, int, int]:
    return _path_stamp(_index_path())


def _copy_record_list(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows if isinstance(row, dict)]


def _load_index_records() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        if not os.path.exists(_index_path()):
            return out
        with open(_index_path(), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
    except Exception:
        return []
    return out


def _index_records_cached() -> List[Dict[str, Any]]:
    stamp = _index_stamp()
    with _CACHE_LOCK:
        if _INDEX_CACHE.get("stamp") == stamp:
            return _copy_record_list(list(_INDEX_CACHE.get("records") or []))

    records = _load_index_records()
    by_doc_id = {
        str(rec.get("doc_id") or "").strip(): dict(rec)
        for rec in records
        if str(rec.get("doc_id") or "").strip()
    }
    with _CACHE_LOCK:
        _INDEX_CACHE["stamp"] = stamp
        _INDEX_CACHE["records"] = _copy_record_list(records)
        _INDEX_CACHE["by_doc_id"] = by_doc_id
    return _copy_record_list(records)


def _index_record_by_doc_id(doc_id: str) -> Optional[Dict[str, Any]]:
    did = str(doc_id or "").strip()
    if not did:
        return None
    _index_records_cached()
    with _CACHE_LOCK:
        rec = dict((_INDEX_CACHE.get("by_doc_id") or {}).get(did) or {})
    return rec or None


def _cached_meta_entry(doc_id: str) -> Optional[Dict[str, Any]]:
    did = str(doc_id or "").strip()
    if not did:
        return None
    path = _meta_path(did)
    stamp = _path_stamp(path)
    with _CACHE_LOCK:
        entry = dict(_META_CACHE.get(did) or {})
    if not entry or entry.get("stamp") != stamp:
        return None
    data = entry.get("data")
    return dict(data) if isinstance(data, dict) else None


def _store_meta_cache(doc_id: str, data: Dict[str, Any]) -> None:
    did = str(doc_id or "").strip()
    if not did:
        return
    with _CACHE_LOCK:
        _META_CACHE[did] = {
            "stamp": _path_stamp(_meta_path(did)),
            "data": dict(data or {}),
        }


def _name_index_entries() -> List[Dict[str, Any]]:
    stamp = _index_stamp()
    with _CACHE_LOCK:
        if _NAME_CACHE.get("stamp") == stamp:
            return _copy_record_list(list(_NAME_CACHE.get("entries") or []))

    entries: List[Dict[str, Any]] = []
    for rec in _index_records_cached():
        doc_id = str(rec.get("doc_id") or "").strip()
        if not doc_id:
            continue
        meta = get_doc_meta(doc_id) or dict(rec)
        try:
            created_at = int(meta.get("created_at") or rec.get("created_at") or 0)
        except Exception:
            created_at = 0
        entries.append(
            {
                "doc_id": doc_id,
                "name": str(meta.get("name") or rec.get("name") or ""),
                "source_name": os.path.basename(str(meta.get("source_path") or rec.get("source_path") or "")),
                "created_at": created_at,
                "meta": dict(meta),
            }
        )
    with _CACHE_LOCK:
        _NAME_CACHE["stamp"] = stamp
        _NAME_CACHE["entries"] = _copy_record_list(entries)
    return _copy_record_list(entries)


def _index_has(doc_id: str) -> bool:
    try:
        if not os.path.exists(_index_path()):
            return False
        with open(_index_path(), "r", encoding="utf-8") as f:
            for line in f:
                if doc_id in line:
                    return True
    except Exception:
        return False
    return False


def _write_index(rec: Dict[str, Any]) -> None:
    try:
        with open(_index_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _normalize_doc_name(name: str) -> str:
    s = unicodedata.normalize("NFKC", str(name or ""))
    s = s.replace("\\", "/").split("/")[-1]
    s = re.sub(r"\s+", " ", s).strip().casefold()
    return s.strip(" ._-\"'`“”«»")


def _doc_name_stem(name: str) -> str:
    base = _normalize_doc_name(name)
    stem, _ = os.path.splitext(base)
    return stem.strip(" ._-")


def _score_doc_name_match(query_name: str, candidate_name: str) -> int:
    q = _normalize_doc_name(query_name)
    c = _normalize_doc_name(candidate_name)
    if not q or not c:
        return 0
    if q == c:
        return 100

    q_stem = _doc_name_stem(q)
    c_stem = _doc_name_stem(c)
    if q_stem and c_stem and q_stem == c_stem:
        return 95
    if q in c or c in q:
        return 70
    if q_stem and c_stem and (q_stem in c_stem or c_stem in q_stem):
        return 60
    return 0


def _scoped_meta_fields(meta: Dict[str, Any]) -> Tuple[str, str]:
    nested = meta.get("meta") if isinstance(meta.get("meta"), dict) else {}
    chat = str(meta.get("chat_id") or nested.get("chat_id") or "").strip()
    user = str(meta.get("user_id") or nested.get("user_id") or "").strip()
    return chat, user


def _meta_matches_scope(
    meta: Dict[str, Any],
    *,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> bool:
    if chat_id is None and user_id is None:
        return True
    chat, user = _scoped_meta_fields(meta)
    if chat_id is not None and chat != str(chat_id):
        return False
    if user_id is not None and user and user != str(user_id):
        return False
    return True


def _tokenize_search(text: str) -> List[str]:
    out: List[str] = []
    seen = set()
    for tok in _SEARCH_TOKEN_RE.findall(str(text or "").casefold()):
        if len(tok) <= 2 or tok in _SEARCH_STOP_TOKENS:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def _safe_source_excerpt(source_path: str, max_chars: int = 2400) -> str:
    path = str(source_path or "").strip()
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(max_chars + 1)
        return " ".join(text.split())[:max_chars]
    except Exception:
        return ""


def build_search_text(
    doc_id: str,
    *,
    meta: Optional[Dict[str, Any]] = None,
    summary: Optional[str] = None,
    chunks: Optional[List[Dict[str, Any]]] = None,
) -> str:
    info = dict(meta or get_doc_meta(doc_id) or {})
    nested = info.get("meta") if isinstance(info.get("meta"), dict) else {}
    name = str(info.get("name") or nested.get("filename") or "")
    title = str(info.get("title") or nested.get("title") or "")
    source_path = str(info.get("source_path") or nested.get("source_path") or "")
    summary_text = str(summary if summary is not None else load_summary(doc_id) or info.get("summary") or "").strip()
    chunk_rows = list(chunks if chunks is not None else load_chunks(doc_id, limit=6))

    parts: List[str] = []
    for value in (name, title, os.path.basename(source_path)):
        value_s = str(value or "").strip()
        if value_s:
            parts.append(value_s)
    if summary_text:
        parts.append(summary_text)

    first_lines = []
    for line in summary_text.splitlines():
        line_s = line.strip()
        if line_s:
            first_lines.append(line_s)
        if len(first_lines) >= 5:
            break
    if first_lines:
        parts.append("\n".join(first_lines))

    for chunk in chunk_rows[:6]:
        text = " ".join(str(chunk.get("text") or "").split()).strip()
        if text:
            parts.append(text[:1200])

    if len(parts) < 3:
        excerpt = _safe_source_excerpt(source_path)
        if excerpt:
            parts.append(excerpt)

    seen = set()
    out: List[str] = []
    for part in parts:
        norm = " ".join(str(part or "").split()).strip()
        if not norm:
            continue
        key = norm.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return "\n".join(out).strip()


def read_search_text(doc_id: str) -> str:
    did = str(doc_id or "").strip()
    if not did:
        return ""
    path = _search_path(did)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read().strip()
    except Exception:
        return ""
    return ""


def ensure_search_text(doc_id: str, *, force: bool = False) -> str:
    did = str(doc_id or "").strip()
    if not did:
        return ""
    _ensure_dirs()
    path = _search_path(did)
    if not force:
        cached = read_search_text(did)
        if cached:
            return cached
    text = build_search_text(did)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass
    return text


def iter_doc_index(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    out = _index_records_cached()
    if limit is None:
        return out
    return out[: max(0, int(limit))]


def get_doc_meta(doc_id: str) -> Optional[Dict[str, Any]]:
    did = str(doc_id or "").strip()
    if not did:
        return None
    cached = _cached_meta_entry(did)
    if cached:
        cached.setdefault("doc_id", did)
        return cached
    path = _meta_path(did)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            if isinstance(data, dict):
                data.setdefault("doc_id", did)
                _store_meta_cache(did, data)
                return data
    except Exception:
        pass
    rec = _index_record_by_doc_id(did)
    if isinstance(rec, dict):
        rec.setdefault("doc_id", did)
        return rec
    return None


def load_summary(doc_id: str) -> str:
    did = str(doc_id or "").strip()
    if not did:
        return ""
    path = _summary_path(did)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read().strip()
    except Exception:
        pass
    meta = get_doc_meta(did) or {}
    return str(meta.get("summary") or "").strip()


def load_chunks(doc_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    did = str(doc_id or "").strip()
    if not did:
        return []
    out: List[Dict[str, Any]] = []
    path = _chunks_path(did)
    try:
        if not os.path.exists(path):
            return out
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
                    if limit is not None and len(out) >= max(0, int(limit)):
                        break
    except Exception:
        return []
    return out


def find_docs_by_name(
    name: str,
    limit: int = 5,
    *,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    query_name = str(name or "").strip()
    if not query_name:
        return []

    scored: List[Tuple[int, int, Dict[str, Any]]] = []
    for entry in _name_index_entries():
        doc_id = str(entry.get("doc_id") or "").strip()
        meta = dict(entry.get("meta") or {})
        rec_name = str(entry.get("name") or "")
        src_name = str(entry.get("source_name") or "")
        score = max(
            _score_doc_name_match(query_name, rec_name),
            _score_doc_name_match(query_name, src_name),
        )
        if score <= 0:
            continue
        if not _meta_matches_scope(meta, chat_id=chat_id, user_id=user_id):
            continue
        created_at = int(entry.get("created_at") or 0)
        scored.append((score, created_at, meta))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [meta for _, _, meta in scored[: max(1, int(limit))]]


def search_docs(
    query: str,
    *,
    limit: int = 5,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    q = " ".join(str(query or "").split()).strip()
    tokens = _tokenize_search(q)
    if not q or not tokens:
        return []

    q_low = q.casefold()
    scored: List[Tuple[float, int, Dict[str, Any]]] = []
    for rec in iter_doc_index():
        doc_id = str(rec.get("doc_id") or "").strip()
        if not doc_id:
            continue
        meta = get_doc_meta(doc_id) or dict(rec)
        if not _meta_matches_scope(meta, chat_id=chat_id, user_id=user_id):
            continue
        text = ensure_search_text(doc_id)
        hay = text.casefold()
        if not hay:
            continue
        token_hits = sum(1 for tok in tokens if tok in hay)
        if token_hits <= 0:
            continue
        score = float(token_hits * 8)
        if q_low in hay:
            score += 20.0
        name = str(meta.get("name") or "")
        title = str(meta.get("title") or (meta.get("meta") or {}).get("title") or "")
        score += max(
            _score_doc_name_match(q, name) * 0.2,
            _score_doc_name_match(q, title) * 0.2,
        )
        created_at = int(meta.get("created_at") or rec.get("created_at") or 0)
        picked = dict(meta)
        picked["_semantic_score"] = score
        scored.append((score, created_at, picked))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [meta for _, _, meta in scored[: max(1, int(limit))]]


def _extract_page(meta: Dict[str, Any]) -> Optional[int]:
    for k in ("page", "page_num", "pageno", "page_index"):
        if k in meta:
            try:
                return int(meta[k])
            except Exception:
                return None
    return None


def _citation(source: str, page: Optional[int]) -> str:
    if page is None or page <= 0:
        return f"[{source} | p. ?]"
    return f"[{source} | p. {page}]"


def _summarize_text(text: str, limit: int = 1200) -> str:
    if not text:
        return ""
    t = " ".join((text or "").split())
    return t[:limit]


def ingest_document(
    raw: bytes,
    orig_name: str,
    full_text: str,
    chunks: List[Dict[str, Any]],
    source_path: str,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    _ensure_dirs()
    doc_id = _doc_id(raw)
    if _index_has(doc_id):
        return doc_id

    meta = meta or {}
    size = len(raw or b"")
    now = int(time.time())

    # Save raw bytes
    raw_path = os.path.join(_docs_root(), "raw", f"{doc_id}.bin")
    try:
        with open(raw_path, "wb") as f:
            f.write(raw)
    except Exception:
        pass

    # Summary
    summary = _summarize_text(full_text)
    summary_path = os.path.join(_docs_root(), "summary", f"{doc_id}.txt")
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)
    except Exception:
        pass

    # Citations + chunks
    citations: List[str] = []
    chunks_path = os.path.join(_docs_root(), "chunks", f"{doc_id}.jsonl")
    try:
        with open(chunks_path, "w", encoding="utf-8") as f:
            for i, ch in enumerate(chunks or []):
                text = (ch.get("text") or "").strip()
                if not text:
                    continue
                page = _extract_page(ch)
                cite = _citation(orig_name, page)
                citations.append(cite)
                rec = {
                    "doc_id": doc_id,
                    "chunk_id": f"{doc_id}:{i}",
                    "text": text,
                    "citation": cite,
                    "meta": ch.get("meta") or {},
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                # Write to memory (parallel, legacy-safe)
                memory_add(
                    "doc_chunk",
                    f"{text}\n{cite}",
                    meta={"doc_id": doc_id, "source": source_path, "citation": cite},
                )
    except Exception:
        pass

    citations = sorted(list(set(citations)))
    citations_path = os.path.join(_docs_root(), "citations", f"{doc_id}.json")
    try:
        with open(citations_path, "w", encoding="utf-8") as f:
            json.dump(citations, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # Meta file
    meta_rec = {
        "doc_id": doc_id,
        "name": orig_name,
        "source_path": source_path,
        "size": size,
        "created_at": now,
        "summary": summary,
        "citations": citations,
        "meta": meta,
    }
    meta_path = os.path.join(_docs_root(), "meta", f"{doc_id}.json")
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_rec, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    try:
        ensure_search_text(doc_id, force=True)
    except Exception:
        pass

    # Index
    _write_index({"doc_id": doc_id, "name": orig_name, "size": size, "source_path": source_path, "created_at": now})

    # Memory summary records
    memory_add("doc", f"{orig_name}", meta={"doc_id": doc_id, "source": source_path, "size": size})
    if summary:
        memory_add("doc_summary", summary, meta={"doc_id": doc_id, "source": source_path})

    return doc_id


def update_summary(doc_id: str, summary: str) -> None:
    if not doc_id:
        return
    _ensure_dirs()
    summary_path = _summary_path(doc_id)
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary or "")
    except Exception:
        pass
    try:
        memory_add("doc_summary", summary or "", meta={"doc_id": doc_id})
    except Exception:
        pass
    try:
        ensure_search_text(doc_id, force=True)
    except Exception:
        pass


def get_citations(doc_id: str) -> List[str]:
    if not doc_id:
        return []
    path = _citations_path(doc_id)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f) or []
            return data if isinstance(data, list) else []
    except Exception:
        return []
    return []


__all__ = [
    "build_search_text",
    "ensure_search_text",
    "find_docs_by_name",
    "get_citations",
    "get_doc_meta",
    "ingest_document",
    "iter_doc_index",
    "load_chunks",
    "load_summary",
    "read_search_text",
    "search_docs",
    "update_summary",
]
