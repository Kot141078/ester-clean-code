# -*- coding: utf-8 -*-
"""ShortTermMemory - kratkosrochnaya pamyat (na sessiyu).
ENV:
  SHORT_TERM_TTL_SEC (by default 3600)
  SHORT_TERM_MAX_ENTRIES (by default 20)
Realizatsiya bez vneshnikh zavisimostey (in-memory) s ochistkoy po TTL."""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TTL = int(os.getenv("SHORT_TERM_TTL_SEC", "3600"))
MAX_ENTRIES = int(os.getenv("SHORT_TERM_MAX_ENTRIES", "20"))


class ShortTermMemory:
    def __init__(self):
        self._store: Dict[str, List[Any]] = {}
        self._ts: Dict[str, float] = {}
        self._lock = threading.RLock()

    def _key(self, user: str, session_id: str) -> str:
        return f"{user or 'default'}::{session_id or 'default'}"

    def _gc(self) -> None:
        now = time.time()
        for k, ts in list(self._ts.items()):
            if now - ts > TTL:
                self._store.pop(k, None)
                self._ts.pop(k, None)

    def add_entry(self, user: str, session_id: str, entry: Any) -> None:
        k = self._key(user, session_id)
        with self._lock:
            self._gc()
            arr = self._store.setdefault(k, [])
            arr.append(entry)
            self._store[k] = arr[-MAX_ENTRIES:]
            self._ts[k] = time.time()

    def get_entries(self, user: str, session_id: str) -> List[Any]:
        k = self._key(user, session_id)
        with self._lock:
            self._gc()
# return list(self._store.get(k, []))