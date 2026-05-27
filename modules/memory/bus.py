# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Iterable, List, Optional


class MemoryBus:
    """Small in-process memory bus used by compatibility tests and guards."""

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        use_vector: bool = False,
        use_chroma: bool = False,
        **_: Any,
    ) -> None:
        self.persist_dir = str(persist_dir or "")
        self.use_vector = bool(use_vector)
        self.use_chroma = bool(use_chroma)
        self._records: List[Dict[str, Any]] = []
        self._closed = False

    def add_record(
        self,
        text: str,
        kind: str = "fact",
        tags: Optional[Iterable[str]] = None,
        **meta: Any,
    ) -> Dict[str, Any]:
        rec: Dict[str, Any] = {
            "id": "mem_" + uuid.uuid4().hex,
            "kind": str(kind or "fact"),
            "type": str(kind or "fact"),
            "text": str(text or ""),
            "tags": [str(tag) for tag in (tags or []) if str(tag).strip()],
            "meta": dict(meta or {}),
            "ts": int(time.time()),
        }
        self._records.append(rec)
        return dict(rec)

    def flashback(self, query: str = "*", k: int = 5) -> List[Dict[str, Any]]:
        limit = max(0, int(k or 0))
        if limit <= 0:
            return []

        needle = str(query or "").strip().lower()
        if not needle or needle == "*":
            return [dict(rec) for rec in self._records[-limit:]]

        hits: List[Dict[str, Any]] = []
        for rec in reversed(self._records):
            haystack = " ".join(
                [
                    str(rec.get("text") or ""),
                    str(rec.get("kind") or ""),
                    " ".join(str(tag) for tag in rec.get("tags") or []),
                ]
            ).lower()
            if needle in haystack:
                hits.append(dict(rec))
            if len(hits) >= limit:
                break
        return hits

    def get_recent_window(self, limit: int = 40) -> List[Dict[str, Any]]:
        count = max(0, int(limit or 0))
        if count <= 0:
            return []
        return [dict(rec) for rec in self._records[-count:]]

    def get_timeline(self, limit: int = 60) -> List[Dict[str, Any]]:
        return self.get_recent_window(limit=limit)

    def readiness_status(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "memory_ready": True,
            "degraded_memory_mode": False,
            "memory_paths": {"persist_dir": self.persist_dir},
            "records": len(self._records),
        }

    def close(self) -> None:
        self._closed = True


__all__ = ["MemoryBus"]
