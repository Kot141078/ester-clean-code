# -*- coding: utf-8 -*-
"""
modules/synergy/telemetry_ingest.py — konveyer ingest'a: kvoty, dedup, bufer → TelemetryEvent.

MOSTY:
- (Yavnyy) Token-bucket na agenta + skolzyaschee okno kheshey dlya deduplikatsii.
- (Skrytyy #1) Bez globalnykh blokirovok: otdelnye legkie struktury per-agent.
- (Skrytyy #2) Vozvraschaet (evt|None, result) — udobno dlya metrik i prichin dropa.

ZEMNOY ABZATs:
Zaschischaet sistemu ot burstov i povtorov: iz «shuma» ostavlyaet tolko poleznye sobytiya,
kotorye idut dalshe v orkestratsiyu/khranilische.

# c=a+b
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from modules.synergy.models import TelemetryEvent
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@dataclass
class IngestResult:
    ok: bool
    reason: str = "ok"  # ok|rate_limited|duplicate
    dropped: bool = False


class _TokenBucket:
    def __init__(self, rate_per_sec: float, burst: float | None = None):
        self.rate = float(rate_per_sec)
        self.capacity = float(burst or rate_per_sec)
        self.tokens = self.capacity
        self.last = time.monotonic()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False


class _DedupWindow:
    def __init__(self, window_ms: int, max_entries: int):
        self.window = window_ms / 1000.0
        self.max = max_entries
        self.buf: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _gc(self):
        cutoff = time.monotonic() - self.window
        for k, ts in list(self.buf.items()):
            if ts < cutoff:
                del self.buf[k]

    def is_duplicate(self, key: str) -> bool:
        with self._lock:
            self._gc()
            if key in self.buf:
                return True
            if len(self.buf) >= self.max:
                # grubaya ochistka poloviny starykh
                items = sorted(self.buf.items(), key=lambda kv: kv[1])
                for k, _ in items[: len(items) // 2]:
                    del self.buf[k]
            self.buf[key] = time.monotonic()
            return False


class TelemetryIngestor:
    def __init__(self):
        self._buckets: Dict[str, _TokenBucket] = {}
        self._dedup: Dict[str, _DedupWindow] = {}
        self._lock = threading.Lock()

    def _get_bucket(self, agent_id: str) -> _TokenBucket:
        rps = float(os.getenv("SYNERGY_TEL_MAX_RPS", "10"))
        with self._lock:
            b = self._buckets.get(agent_id)
            if b is None:
                b = _TokenBucket(rate_per_sec=rps, burst=rps)
                self._buckets[agent_id] = b
            return b

    def _get_window(self, agent_id: str) -> _DedupWindow:
        win = int(os.getenv("SYNERGY_TEL_DEDUP_WINDOW_MS", "1500"))
        cap = int(os.getenv("SYNERGY_TEL_BUFFER", "256"))
        with self._lock:
            w = self._dedup.get(agent_id)
            if w is None:
                w = _DedupWindow(window_ms=win, max_entries=cap)
                self._dedup[agent_id] = w
            return w

    @staticmethod
    def _hash_event(evt: TelemetryEvent) -> str:
        h = hashlib.sha256()
        # Svodim klyuchevye polya v khesh
        parts = [
            evt.agent_id,
            str(evt.vendor or ""),
            str(round(float(evt.latency_ms or 0.0), 3)),
            str(round(float(evt.flight_time_min or 0.0), 2)),
            str(round(float(evt.payload_g or 0.0), 1)),
        ]
        h.update(("|".join(parts)).encode("utf-8"))
        return h.hexdigest()

    def ingest(self, agent_id: str, evt: TelemetryEvent) -> Tuple[Optional[TelemetryEvent], IngestResult]:
        # Kvoty
        if not self._get_bucket(agent_id).allow():
            return None, IngestResult(ok=False, reason="rate_limited", dropped=True)

        # Deduplikatsiya
        key = self._hash_event(evt)
        if self._get_window(agent_id).is_duplicate(key):
            return None, IngestResult(ok=False, reason="duplicate", dropped=True)

        return evt, IngestResult(ok=True, reason="ok", dropped=False)