# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from modules.dreams.store import DreamStore

_STOP_WORDS = {
    "the",
    "and",
    "or",
    "to",
    "for",
    "of",
    "in",
    "on",
    "a",
    "an",
    "is",
    "it",
    "this",
    "that",
    "i",
    "v",
    "na",
    "s",
    "po",
    "kak",
    "chto",
    "eto",
    "k",
    "iz",
}


def _now_iso(ts: Optional[float] = None) -> str:
    value = float(ts if ts is not None else time.time())
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[0-9a-zA-Za-yaA-YaeE_]+", str(text or "").lower())


def _top_keywords(rows: List[Dict[str, Any]], n: int = 6) -> List[str]:
    freq: Dict[str, int] = {}
    for row in rows:
        for tok in _tokenize(str(row.get("text") or "")):
            if len(tok) < 3 or tok in _STOP_WORDS:
                continue
            freq[tok] = int(freq.get(tok, 0)) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[: max(1, int(n or 6))]]


class DreamRunner:
    def __init__(self, persist_dir: Optional[str] = None) -> None:
        self.store = DreamStore(persist_dir=persist_dir)
        self.window_size = max(5, int(os.getenv("ESTER_DREAM_WINDOW", "40") or 40))
        self.timeline_limit = max(5, int(os.getenv("ESTER_DREAM_TIMELINE", "60") or 60))

    def _compose_text(self, window: List[Dict[str, Any]], timeline: List[Dict[str, Any]]) -> str:
        if not window and not timeline:
            return "Dream fallback: no recent memory traces were available."

        keywords = _top_keywords(window or timeline, n=6)
        head = ", ".join(keywords) if keywords else "memory patterns"

        snippets: List[str] = []
        for rec in (window or timeline)[:3]:
            text = str(rec.get("text") or "").strip()
            if not text:
                continue
            snippets.append(text[:180])
        joined = " | ".join(snippets) if snippets else "quiet interval"

        return f"Dream summary on {head}: {joined}"

    def run_once(
        self,
        memory_bus: Any,
        now_ts: Optional[float] = None,
        budgets: Optional[Dict[str, Any]] = None,
        dry: bool = False,
    ) -> Dict[str, Any]:
        ts = float(now_ts if now_ts is not None else time.time())
        budgets = dict(budgets or {})
        window_k = max(1, int(budgets.get("window", self.window_size) or self.window_size))
        timeline_k = max(1, int(budgets.get("timeline", self.timeline_limit) or self.timeline_limit))

        try:
            window = list(memory_bus.get_recent_window(limit=window_k))
            timeline = list(memory_bus.get_timeline(limit=timeline_k))
            text = self._compose_text(window, timeline)

            ids = [str(x.get("id") or "") for x in window[:50]]
            digest = hashlib.sha1("|".join(ids).encode("utf-8", errors="ignore")).hexdigest()[:12]
            source_meta = {
                "window_count": len(window),
                "timeline_count": len(timeline),
                "window_min_ts": min([int(x.get("ts") or 0) for x in window], default=0),
                "window_max_ts": max([int(x.get("ts") or 0) for x in window], default=0),
                "window_hash": digest,
            }

            record = {
                "id": "dream_" + uuid.uuid4().hex,
                "ts": _now_iso(ts),
                "text": text,
                "tags": ["dream", "offline", "normal_memory"],
                "source_window_meta": source_meta,
                "ok": True,
                "error": "",
            }
            if not dry:
                self.store.append(record)

            return {
                "ok": True,
                "record": record,
                "stored": bool(not dry),
                "path": str(self.store.path),
                "last_count": int(source_meta["window_count"]),
            }
        except Exception as exc:
            err = str(exc)
            record = {
                "id": "dream_" + uuid.uuid4().hex,
                "ts": _now_iso(ts),
                "text": "",
                "tags": ["dream", "offline", "error"],
                "source_window_meta": {},
                "ok": False,
                "error": err,
            }
            if not dry:
                self.store.append(record)
            return {
                "ok": False,
                "record": record,
                "stored": bool(not dry),
                "path": str(self.store.path),
                "last_count": 0,
                "error": err,
            }
