# -*- coding: utf-8 -*-
"""
security/nonce_store.py — TTL-khranilische odnorazovykh znacheniy (replay guard).

MOSTY:
- (Yavnyy) check_and_remember(token, ttl) — True, esli novyy; False, esli povtor (replay).
- (Skrytyy #1) Ogranichenie razmera i LRU-ochistka bez vneshnikh zavisimostey.
- (Skrytyy #2) Potokobezopasnost (RLock), TTL po monotonnym chasam.

ZEMNOY ABZATs:
Blokiruet povtornuyu otpravku togo zhe zaprosa v fiksirovannom okne (napr., 10 minut), dazhe esli podpis i metka vremeni byli validny.

# c=a+b
"""
from __future__ import annotations
import os, time, threading
from typing import Dict, Tuple, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class NonceStore:
    def __init__(self, max_items: int = None):
        self._max = int(max_items or int(os.getenv("P2P_NONCE_MAX", "50000")))
        self._d: Dict[str, Tuple[float, float]] = {}  # token -> (exp, last_access)
        self._lock = threading.RLock()

    def _evict_if_needed(self):
        if len(self._d) <= self._max:
            return
        # udalit ~10% samykh starykh po last_access
        n = max(1, self._max // 10)
        items = sorted(self._d.items(), key=lambda kv: kv[1][1])[:n]
        for k,_ in items:
            self._d.pop(k, None)

    def check_and_remember(self, token: str, ttl_sec: float) -> bool:
        now = time.monotonic()
        exp = now + float(ttl_sec)
        with self._lock:
            rec = self._d.get(token)
            if rec:
                if rec[0] > now:
                    # esche ne istek — replay
                    return False
            self._d[token] = (exp, now)
            self._evict_if_needed()
            return True

    def cleanup(self):
        now = time.monotonic()
        with self._lock:
            for k,(exp,_) in list(self._d.items()):
                if exp <= now:
                    self._d.pop(k, None)

STORE = NonceStore()