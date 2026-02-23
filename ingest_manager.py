# -*- coding: utf-8 -*-
from __future__ import annotations

"""
IngestManager — prostoy menedzher inzhesta faylov v vstore.

Tseli:
- ne padat iz-za kodirovok/otsutstvuyuschikh moduley;
- davat stabilnyy job-status;
- po umolchaniyu rabotat sinkhronno (udobno dlya testov i CLI);
- ne navyazyvat konkretnyy VectorStore: dostatochno metodov add_texts()/upsert_texts().

API:
  submit_file(path) -> job_id
  submit_bytes(name, raw_bytes) -> job_id
  list_jobs() -> [ {id,status,source,created,updated,count,error?} ]
  get_job(job_id) -> dict|None
"""

import os
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_STATUS_QUEUED = "QUEUED"
_STATUS_DONE = "DONE"
_STATUS_ERROR = "ERROR"


def _safe_basename(p: str) -> str:
    try:
        return os.path.basename(p) or p
    except Exception:
        return p


def _chunk_file_fallback(path: str, *, max_chars: int = 1800, overlap: int = 200) -> List[str]:
    """Esli file_chunker ne dostupen — delaem prostoy chanking po simvolam s perekrytiem."""
    try:
        raw = open(path, "rb").read()
    except Exception:
        return []

    # Poprobuem neskolko dekoderov (bez zavisimosti ot locale)
    text = ""
    for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1251", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue

    if not text.strip():
        # poslednyaya popytka — zamenyaem oshibki
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            return []

    text = text.replace("\r\n", "\n")
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    i = 0
    n = len(text)
    step = max(1, max_chars - overlap)
    while i < n:
        chunks.append(text[i : i + max_chars])
        i += step
    return [c for c in chunks if c.strip()]


def _chunk_file(path: str) -> List[str]:
    """Predpochtitelno ispolzuem file_chunker.chunk_file, inache fallback."""
    try:
        from file_chunker import chunk_file  # type: ignore

        chunks = chunk_file(path)
        if isinstance(chunks, list) and all(isinstance(x, str) for x in chunks):
            return [c for c in chunks if c.strip()]
    except Exception:
        pass
    return _chunk_file_fallback(path)


def _vstore_add(vstore: Any, texts: Sequence[str], meta: Dict[str, Any], ids: Optional[Sequence[str]] = None) -> None:
    """Probuem raznye metody vstore dlya sovmestimosti."""
    if not texts:
        return

    # 1) upsert_texts(texts, ids=[...], meta=...)
    if hasattr(vstore, "upsert_texts"):
        try:
            vstore.upsert_texts(list(texts), ids=list(ids) if ids else None, meta=meta)
            return
        except Exception:
            pass

    # 2) add_texts(texts, meta=...)
    if hasattr(vstore, "add_texts"):
        vstore.add_texts(list(texts), meta=meta)
        return

    raise AttributeError("vstore must provide add_texts() or upsert_texts()")


class IngestManager:
    def __init__(
        self,
        vstore: Any,
        watch_dirs: Optional[List[str]] = None,
        inbox_dir: Optional[str] = None,
    ):
        self.vstore = vstore
        self.watch_dirs = list(watch_dirs or [])
        self.inbox_dir = inbox_dir or ""
        if self.inbox_dir:
            os.makedirs(self.inbox_dir, exist_ok=True)
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def submit_file(self, path: str, *, meta: Optional[Dict[str, Any]] = None) -> str:
        """Indeksiruet odin fayl sinkhronno."""
        jid = uuid.uuid4().hex
        now = time.time()
        job: Dict[str, Any] = {
            "id": jid,
            "status": _STATUS_QUEUED,
            "source": path,
            "created": now,
            "updated": now,
            "count": 0,
        }
        self._jobs[jid] = job

        try:
            if not os.path.isfile(path):
                raise FileNotFoundError(path)

            chunks = _chunk_file(path)
            # Determinirovannye id dlya chankov (chtoby povtornyy inzhest ne plodil dubley)
            ids = [f"{jid}:{i}" for i in range(len(chunks))]

            m = {"source": _safe_basename(path)}
            if meta:
                m.update(meta)

            _vstore_add(self.vstore, chunks, m, ids=ids)

            job["count"] = len(chunks)
            job["status"] = _STATUS_DONE
            job["updated"] = time.time()
        except Exception as e:
            job["status"] = _STATUS_ERROR
            job["error"] = str(e)
            job["updated"] = time.time()

        return jid

    def submit_bytes(self, name: str, raw: bytes, *, meta: Optional[Dict[str, Any]] = None) -> str:
        """
        Udobno dlya REST: prinyat bytes, sokhranit v inbox_dir (esli zadan) i proindeksirovat.
        """
        jid = uuid.uuid4().hex
        now = time.time()
        job: Dict[str, Any] = {
            "id": jid,
            "status": _STATUS_QUEUED,
            "source": name,
            "created": now,
            "updated": now,
            "count": 0,
        }
        self._jobs[jid] = job

        try:
            if self.inbox_dir:
                os.makedirs(self.inbox_dir, exist_ok=True)
                path = os.path.join(self.inbox_dir, name)
                with open(path, "wb") as f:
                    f.write(raw)
                return self.submit_file(path, meta=meta)

            text = ""
            for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1251", "latin-1"):
                try:
                    text = raw.decode(enc)
                    break
                except Exception:
                    pass
            if not text:
                text = raw.decode("utf-8", errors="replace")

            chunks = [text] if text.strip() else []
            ids = [f"{jid}:0"] if chunks else []

            m = {"source": name}
            if meta:
                m.update(meta)

            _vstore_add(self.vstore, chunks, m, ids=ids)

            job["count"] = len(chunks)
            job["status"] = _STATUS_DONE
            job["updated"] = time.time()
        except Exception as e:
            job["status"] = _STATUS_ERROR
            job["error"] = str(e)
            job["updated"] = time.time()

        return jid

    def list_jobs(self) -> List[Dict[str, Any]]:
        return sorted(self._jobs.values(), key=lambda j: j.get("created", 0.0), reverse=True)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._jobs.get(job_id)