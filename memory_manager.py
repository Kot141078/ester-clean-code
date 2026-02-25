# -*- coding: utf-8 -*-
from __future__ import annotations

"""memory_manager.py - koordinatsiya neskolkikh sloev pamyati.

Sovmestimost:
- podderzhivaet legacy API iz starykh testov (add_to_medium_term(user, q, a, emotions, tags),
  long_term.size, medium_term.memory, offers/agenda methodology);
- podderzhivaet tekuschiy API add_to_medium_term(user, item_dict)."""

from datetime import datetime, timedelta
import logging
import math
import time
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)


class _MediumTermAdapter:
    def __init__(self) -> None:
        self.memory: Dict[str, List[Dict[str, Any]]] = {}


class _LongTermAdapter:
    def __init__(self, vstore: Any) -> None:
        self._vstore = vstore

    @property
    def size(self) -> int:
        try:
            if hasattr(self._vstore, "size") and callable(getattr(self._vstore, "size")):
                val = self._vstore.size()
                if isinstance(val, int):
                    return max(0, val)
                return max(0, int(val))
        except Exception:
            pass
        try:
            if hasattr(self._vstore, "__len__"):
                return max(0, int(len(self._vstore)))
        except Exception:
            pass
        return 0


def _now_iso() -> str:
    return datetime.now().isoformat()


def _parse_ts_like(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except Exception:
        pass
    try:
        # tolerant for trailing Z
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return float(datetime.fromisoformat(s).timestamp())
    except Exception:
        return 0.0


class MemoryManager:
    DEFAULT_SHORT_LIMIT_PER_SESSION = 100
    DEFAULT_SHORT_TTL_SECONDS = None  # None = no expiry

    def __init__(
        self,
        vstore,
        structured_mem,
        cards,
        short_limit_per_session: int = DEFAULT_SHORT_LIMIT_PER_SESSION,
        short_ttl_seconds: Optional[float] = DEFAULT_SHORT_TTL_SECONDS,
    ):
        self.vstore = vstore
        self.structured = structured_mem
        self.medium_cards = cards

        # Legacy compatibility surfaces expected by tests.
        self.medium_term = _MediumTermAdapter()
        self.long_term = _LongTermAdapter(vstore)

        self.short_limit_per_session = max(1, int(short_limit_per_session))
        self.short_ttl_seconds = short_ttl_seconds if (short_ttl_seconds is None or short_ttl_seconds > 0) else None

        self._short: Dict[str, List[Dict[str, Any]]] = {}
        self._offers: Dict[str, List[Dict[str, Any]]] = {}

    # ---- short memory ----
    def add_to_short_term(self, user: str, session_id: str, item: Dict[str, Any]) -> None:
        key = f"{user}|{session_id}"
        now = time.time()
        rec = dict(item or {})
        rec["ts"] = float(rec.get("ts", now))

        buf = self._short.setdefault(key, [])
        buf.append(rec)

        self._prune_short_buffer(key)
        self._short[key] = self._short[key][-self.short_limit_per_session :]

    def get_short_term(self, user: str, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        key = f"{user}|{session_id}"
        self._prune_short_buffer(key)
        buf = self._short.get(key, [])
        return buf[-max(0, int(limit)) :] if limit is not None else list(buf)

    def clear_short_term(self, user: str, session_id: str) -> None:
        key = f"{user}|{session_id}"
        self._short.pop(key, None)

    # ---- medium/long memory ----
    def add_to_medium_term(self, user: str, *args: Any, **kwargs: Any) -> str:
        """
        Supported signatures:
        1) add_to_medium_term(user, item_dict)
        2) add_to_medium_term(user, query, answer, emotions, tags)
        """
        query = ""
        answer = ""
        emotions: Dict[str, Any] = {}
        tags: List[Any] = []

        if args and isinstance(args[0], dict) and len(args) == 1:
            item = dict(args[0] or {})
            query = str(item.get("query") or item.get("q") or "").strip()
            answer = str(item.get("answer") or item.get("text") or "").strip()
            emotions = dict(item.get("emotions") or item.get("affect") or {})
            tags = list(item.get("tags") or [])
            try:
                weight = float(item.get("weight", kwargs.get("weight", 0.5)))
            except Exception:
                weight = 0.5
        else:
            query = str(args[0] if len(args) > 0 else kwargs.get("query", "")).strip()
            answer = str(args[1] if len(args) > 1 else kwargs.get("answer", "")).strip()
            maybe_emotions = args[2] if len(args) > 2 else kwargs.get("emotions", {})
            emotions = dict(maybe_emotions or {}) if isinstance(maybe_emotions, dict) else {}
            maybe_tags = args[3] if len(args) > 3 else kwargs.get("tags", [])
            tags = list(maybe_tags or []) if isinstance(maybe_tags, list) else []
            try:
                weight = float(kwargs.get("weight", 0.5))
            except Exception:
                weight = 0.5

        entry = {
            "query": query,
            "answer": answer,
            "emotions": emotions,
            "tags": list(tags),
            "weight": max(0.0, min(1.0, float(weight))),
            "timestamp": _now_iso(),
        }
        self.medium_term.memory.setdefault(str(user or "default"), []).append(entry)

        text = answer or query
        if not text:
            return ""

        rid = ""
        try:
            rid = str(
                self.structured.add_record(
                    text=text,
                    tags=list(tags),
                    weight=float(entry["weight"]),
                )
            )
        except Exception:
            log.exception("structured.add_record failed")

        self._vstore_add_text(user=user, text=text, tags=list(tags))
        return rid

    def add_to_long_term(self, text: str, user: str = "default", tags: Optional[List[Any]] = None) -> bool:
        txt = str(text or "").strip()
        if not txt:
            return False
        self._vstore_add_text(user=user, text=txt, tags=list(tags or []))
        try:
            self.structured.add_record(text=txt, tags=list(tags or []), weight=0.5)
        except Exception:
            pass
        return True

    def compact_short_to_medium(self) -> int:
        moved = 0
        keys = list(self._short.keys())
        for key in keys:
            buf = self._short.get(key) or []
            if not buf:
                continue
            user = key.split("|", 1)[0]
            parts: List[str] = []
            for item in buf:
                msg = str(item.get("msg") or item.get("text") or "").strip()
                if msg:
                    parts.append(msg)
            if parts:
                self.add_to_medium_term(user, "\n".join(parts), "", {}, ["short_term"])
                moved += 1
            self._short.pop(key, None)
        return moved

    def gc_expired(self, days: int = 90) -> int:
        cutoff = time.time() - max(1, int(days)) * 86400
        removed = 0
        for user, items in list(self.medium_term.memory.items()):
            kept: List[Dict[str, Any]] = []
            for it in items:
                ts = _parse_ts_like(it.get("timestamp") or it.get("ts"))
                if ts and ts < cutoff:
                    removed += 1
                    continue
                kept.append(it)
            self.medium_term.memory[user] = kept
        return removed

    def apply_decay(self, user: str, half_life_days: float = 30.0) -> int:
        items = self.medium_term.memory.get(user, [])
        changed = 0
        hl = max(0.1, float(half_life_days))
        for it in items:
            try:
                w = float(it.get("weight", 1.0))
            except Exception:
                w = 1.0
            ts = _parse_ts_like(it.get("timestamp") or it.get("ts"))
            if ts <= 0:
                continue
            age_days = max(0.0, (time.time() - ts) / 86400.0)
            factor = math.pow(0.5, age_days / hl)
            new_w = max(0.0, min(1.0, w * factor))
            if new_w != w:
                it["weight"] = new_w
                changed += 1
        return changed

    # ---- offers / initiatives ----
    def record_offers(self, user: str, offers: List[Dict[str, Any]]) -> int:
        uid = str(user or "default")
        arr = self._offers.setdefault(uid, [])
        for off in offers or []:
            item = dict(off or {})
            item.setdefault("timestamp", _now_iso())
            arr.append(item)
        return len(arr)

    def get_agenda(self, user: str) -> List[Dict[str, Any]]:
        uid = str(user or "default")
        now = time.time()
        out: List[Dict[str, Any]] = []
        for it in self._offers.get(uid, []):
            st = str(it.get("status") or "pending").lower()
            if st not in {"pending", "snoozed"}:
                continue
            until_ts = _parse_ts_like(it.get("until"))
            if until_ts and until_ts < now and st == "snoozed":
                continue
            out.append(dict(it))
        return out

    def mark_offer(self, user: str, oid: str, status: str) -> bool:
        uid = str(user or "default")
        target = str(oid or "")
        for it in self._offers.get(uid, []):
            if str(it.get("id") or "") == target:
                it["status"] = str(status or "pending")
                it["updated_at"] = _now_iso()
                return True
        return False

    def snooze_offer(self, user: str, oid: str, minutes: int) -> bool:
        uid = str(user or "default")
        target = str(oid or "")
        until = datetime.now() + timedelta(minutes=max(1, int(minutes or 1)))
        for it in self._offers.get(uid, []):
            if str(it.get("id") or "") == target:
                it["status"] = "snoozed"
                it["until"] = until.isoformat()
                it["updated_at"] = _now_iso()
                return True
        return False

    def get_offers_history(self, user: str, since: Optional[str] = None) -> List[Dict[str, Any]]:
        uid = str(user or "default")
        cutoff = _parse_ts_like(since) if since else 0.0
        out: List[Dict[str, Any]] = []
        for it in self._offers.get(uid, []):
            ts = _parse_ts_like(it.get("timestamp") or it.get("updated_at"))
            if cutoff and ts and ts < cutoff:
                continue
            out.append(dict(it))
        return out

    def heal_all(self) -> Dict[str, Any]:
        vfix = 0
        mfix = 0
        try:
            if hasattr(self.vstore, "repair") and callable(getattr(self.vstore, "repair")):
                rep = self.vstore.repair()
                vfix = 1 if rep else 0
        except Exception:
            vfix = 0
        try:
            rep2 = self.structured.compact(dry_run=False)
            mfix = int(rep2.get("deleted", 0)) + int(rep2.get("merged", 0))
        except Exception:
            mfix = 0
        return {"vstore_fixed": vfix, "mem_fixed": mfix}

    def update_meta_memory(self, days: int = 7) -> Dict[str, Any]:
        cutoff = time.time() - max(1, int(days)) * 86400
        items: List[Dict[str, Any]] = []
        for arr in self.medium_term.memory.values():
            for it in arr:
                ts = _parse_ts_like(it.get("timestamp") or it.get("ts"))
                if ts and ts >= cutoff:
                    items.append(it)

        mood_values: List[float] = []
        for it in items:
            emo = it.get("emotions") or {}
            if isinstance(emo, dict):
                for v in emo.values():
                    try:
                        mood_values.append(float(v))
                    except Exception:
                        continue

        mood_avg = (sum(mood_values) / len(mood_values)) if mood_values else 0.0
        msgs_per_day = float(len(items)) / float(max(1, int(days)))
        return {
            "mood_avg": mood_avg,
            "msgs_per_day": msgs_per_day,
            "events": len(items),
            "days": int(days),
        }

    @staticmethod
    def sample_rule_priority(rule: Dict[str, Any]) -> float:
        try:
            accepts = max(0.0, float(rule.get("accepts", 0.0)))
            dismisses = max(0.0, float(rule.get("dismisses", 0.0)))
        except Exception:
            return 0.0
        total = accepts + dismisses
        if total <= 0:
            return 0.5
        return max(0.0, min(1.0, accepts / total))

    def explain_offer(self, offer: Dict[str, Any], user: str) -> str:
        reason = str((offer or {}).get("reason") or "")
        rule = str((offer or {}).get("rule") or "")
        hist_n = len(self.get_offers_history(user))
        parts = ["Predlozhenie sformirovano na osnove istorii."]
        if reason:
            parts.append(f"Prichina: {reason}.")
        if rule:
            parts.append(f"Pravilo: {rule}.")
        parts.append(f"Zapisey v istorii: {hist_n}.")
        return " ".join(parts)

    # ---- flashback / alias / compact ----
    def flashback(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        k = max(1, int(k))
        query = str(query or "").strip()
        if not query:
            return []

        try:
            s_hits = self.structured.flashback(query, k=k) or []
        except Exception:
            log.exception("structured.flashback failed")
            s_hits = []

        s_hits_norm = [self._normalize_hit(h, source="structured") for h in s_hits if isinstance(h, dict)]

        if len(s_hits_norm) < k:
            rest = k - len(s_hits_norm)
            try:
                v_hits = self.vstore.search(query, k=rest) or []
            except Exception:
                log.exception("vstore.search failed")
                v_hits = []

            for h in v_hits:
                if isinstance(h, dict):
                    s_hits_norm.append(self._normalize_hit(h, source="vstore"))

        for i, h in enumerate(s_hits_norm):
            if not h.get("id"):
                h["id"] = f"fb_{i}"

        s_hits_norm.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
        return s_hits_norm[:k]

    def alias(self, doc_id: str, new_id: str) -> Dict[str, Any]:
        return self.structured.alias(doc_id, new_id)

    def compact(self, dry_run: bool = True) -> Dict[str, Any]:
        return self.structured.compact(dry_run=dry_run)

    # ---- stats ----
    def stats(self) -> Dict[str, Any]:
        short_buffers = 0
        try:
            self._prune_all_short()
            short_buffers = sum(len(v) for v in self._short.values())
        except Exception:
            short_buffers = 0

        try:
            structured_stats = self.structured.stats()
        except Exception:
            structured_stats = {}

        vstore_docs = None
        try:
            if hasattr(self.vstore, "size") and callable(getattr(self.vstore, "size")):
                vstore_docs = self.vstore.size()
            elif hasattr(self.vstore, "__len__"):
                vstore_docs = len(self.vstore)
            elif hasattr(self.vstore, "count") and callable(getattr(self.vstore, "count")):
                vstore_docs = self.vstore.count()
        except Exception:
            vstore_docs = None

        return {
            "short_buffers": short_buffers,
            "structured": structured_stats,
            "vstore_docs": vstore_docs,
        }

    # ---- internal helpers ----
    def _normalize_hit(self, h: Dict[str, Any], source: str) -> Dict[str, Any]:
        text = h.get("text")
        if text is None:
            text = h.get("content")
        text = "" if text is None else str(text)

        score = h.get("score")
        if score is None:
            score = h.get("similarity")
        try:
            score_f = float(score) if score is not None else 0.0
        except Exception:
            score_f = 0.0

        tags = h.get("tags")
        if not isinstance(tags, list):
            tags = []

        try:
            weight = float(h.get("weight", 0.5))
        except Exception:
            weight = 0.5

        out = dict(h)
        out.setdefault("id", h.get("id"))
        out["text"] = text
        out["score"] = score_f
        out["tags"] = tags
        out["weight"] = weight
        out["source"] = source
        return out

    def _vstore_add_text(self, user: str, text: str, tags: List[Any]) -> None:
        meta = {"user": user, "tags": tags}
        try:
            if hasattr(self.vstore, "add_texts") and callable(getattr(self.vstore, "add_texts")):
                try:
                    self.vstore.add_texts([text], meta=meta)
                except TypeError:
                    self.vstore.add_texts([text], metadatas=[meta])
            elif hasattr(self.vstore, "add") and callable(getattr(self.vstore, "add")):
                self.vstore.add([text], [meta])
        except Exception:
            log.exception("vstore.add_text failed (non-critical)")

    def _prune_short_buffer(self, key: str) -> None:
        if self.short_ttl_seconds is None:
            return

        buf = self._short.get(key)
        if not buf:
            return

        now = time.time()
        cutoff = now - self.short_ttl_seconds
        new_buf = [item for item in buf if item.get("ts", 0) > cutoff]

        if len(new_buf) != len(buf):
            self._short[key] = new_buf

    def _prune_all_short(self) -> None:
        if self.short_ttl_seconds is None:
            return

        keys = list(self._short.keys())
        for k in keys:
            self._prune_short_buffer(k)
            if not self._short.get(k):
                self._short.pop(k, None)
