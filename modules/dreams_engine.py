# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from modules.dreams.dream_engine import DreamRunner


class _CountList(list):
    """List that is also comparable to integer thresholds by its length."""

    def _cmp_len(self, other: Any, op) -> Any:
        if isinstance(other, (int, float)):
            return op(len(self), int(other))
        return NotImplemented

    def __ge__(self, other: Any) -> Any:
        return self._cmp_len(other, lambda a, b: a >= b)

    def __gt__(self, other: Any) -> Any:
        return self._cmp_len(other, lambda a, b: a > b)

    def __le__(self, other: Any) -> Any:
        return self._cmp_len(other, lambda a, b: a <= b)

    def __lt__(self, other: Any) -> Any:
        return self._cmp_len(other, lambda a, b: a < b)

    def __eq__(self, other: Any) -> Any:
        if isinstance(other, (int, float)):
            return len(self) == int(other)
        return super().__eq__(other)

    def __int__(self) -> int:
        return len(self)


def _as_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        out = int(value)
    except Exception:
        out = int(default)
    return max(minimum, out)


@dataclass
class DreamRule:
    query: str = "*"
    k: int = 200
    ngram: int = 3
    min_cluster_size: int = 2
    max_hypotheses_per_cluster: int = 2
    topic_hint: Optional[str] = None

    def __init__(
        self,
        query: str = "*",
        k: int = 200,
        ngram: int = 3,
        min_cluster_size: int = 2,
        max_hypotheses_per_cluster: int = 2,
        topic_hint: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.query = str(query or "*")
        self.k = _as_int(kwargs.get("top_k", k), 200, 1)
        self.ngram = _as_int(ngram, 3, 1)
        self.min_cluster_size = _as_int(min_cluster_size, 2, 1)
        self.max_hypotheses_per_cluster = _as_int(max_hypotheses_per_cluster, 2, 1)
        self.topic_hint = str(topic_hint).strip() if topic_hint else None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "k": self.k,
            "ngram": self.ngram,
            "min_cluster_size": self.min_cluster_size,
            "max_hypotheses_per_cluster": self.max_hypotheses_per_cluster,
            "topic_hint": self.topic_hint,
        }


class _CompatBus:
    def __init__(self, mm: Any, text: str = "") -> None:
        self.mm = mm
        self.text = str(text or "").strip()

    def _collect(self, limit: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if self.text:
            out.append({"id": "payload_1", "text": self.text, "ts": int(time.time())})

        fn = getattr(self.mm, "flashback", None)
        if callable(fn):
            rows: List[Any] = []
            for call in (
                lambda: fn(query="*", k=limit),
                lambda: fn("*", limit),
                lambda: fn("*"),
            ):
                try:
                    data = call()
                    if isinstance(data, list):
                        rows = data
                        break
                except Exception:
                    continue
            for idx, rec in enumerate(rows):
                if isinstance(rec, dict):
                    txt = str(rec.get("text") or rec.get("content") or "").strip()
                    if not txt:
                        continue
                    out.append(
                        {
                            "id": str(rec.get("id") or f"legacy_{idx}"),
                            "text": txt,
                            "ts": int(rec.get("ts") or rec.get("mtime") or 0),
                        }
                    )
                else:
                    txt = str(rec or "").strip()
                    if txt:
                        out.append({"id": f"legacy_{idx}", "text": txt, "ts": 0})
        return out[: max(1, int(limit or 40))]

    def get_recent_window(self, limit: int = 40) -> List[Dict[str, Any]]:
        return self._collect(limit)

    def get_timeline(self, limit: int = 60) -> List[Dict[str, Any]]:
        return self._collect(limit)



def _normalize_rules(rules: Any) -> List[DreamRule]:
    if rules is None:
        return [DreamRule()]
    if isinstance(rules, DreamRule):
        return [rules]
    if isinstance(rules, dict):
        return [DreamRule(**rules)]
    if isinstance(rules, str):
        return [DreamRule(query=rules)]
    if isinstance(rules, Iterable):
        out: List[DreamRule] = []
        for item in rules:
            if isinstance(item, DreamRule):
                out.append(item)
            elif isinstance(item, dict):
                out.append(DreamRule(**item))
            else:
                out.append(DreamRule(query=str(item or "*")))
        return out or [DreamRule()]
    return [DreamRule()]


class DreamsEngine:
    """
    Legacy-compatible wrapper over canonical DreamRunner (Iter19).
    """

    def __init__(self, mm: Any, provider: Any = None, **kwargs: Any) -> None:
        self.mm = mm
        self.provider = provider
        self.kwargs = dict(kwargs or {})
        persist_dir = self.kwargs.get("persist_dir") or os.getenv("PERSIST_DIR")
        self.default_dry = bool(self.kwargs.get("dry", False))
        self.runner = DreamRunner(persist_dir=str(persist_dir) if persist_dir else None)

    def run(self, rules: Any = None) -> Dict[str, Any]:
        rule = _normalize_rules(rules)[0]
        bus = _CompatBus(self.mm)
        dry = bool(self.default_dry)
        rep = self.runner.run_once(
            bus,
            dry=dry,
            budgets={
                "window": int(rule.k),
                "timeline": max(60, int(rule.k)),
            },
        )

        text = str((rep.get("record") or {}).get("text") or "").strip()
        clusters: _CountList = _CountList()
        hypotheses: _CountList = _CountList()
        if text:
            clusters = _CountList(
                [
                {
                    "id": "cluster_1",
                    "key": str(rule.topic_hint or "dream"),
                    "size": 1,
                    "query": rule.query,
                    "items": [{"id": "dream_record", "text": text, "mtime": 0.0}],
                }
                ]
            )
            hypotheses = _CountList(
                [
                {
                    "id": "hyp_1",
                    "cluster_id": "cluster_1",
                    "topic": str(rule.topic_hint or "dream"),
                    "text": f"Klaster: {text}",
                    "score": 0.5,
                    "source_id": "dream_record",
                }
                ]
            )

        persisted_hyp = 0
        if hypotheses and not dry:
            try:
                from memory.hypothesis_store import HypothesisStore
                from memory.kg_store import KGStore

                hs = HypothesisStore()
                kg = KGStore()
                kg_nodes: List[Dict[str, Any]] = []
                kg_edges: List[Dict[str, Any]] = []
                now_ts = float(time.time())

                for h in hypotheses:
                    h_text = str(h.get("text") or "").strip()
                    if not h_text:
                        continue
                    topic = str(h.get("topic") or rule.topic_hint or "dream")
                    tags = ["dream", "hypothesis", "offline"]
                    hid = hs.add(text=h_text, topic=topic, tags=tags, score=float(h.get("score") or 0.5))
                    persisted_hyp += 1
                    kg_nodes.append(
                        {
                            "id": f"hyp::{hid}",
                            "type": "hypothesis",
                            "label": f"Hypothesis {hid}",
                            "props": {
                                "text": h_text,
                                "topic": topic,
                                "source": "dreams_engine",
                                "cluster_id": str(h.get("cluster_id") or ""),
                            },
                            "mtime": now_ts,
                        }
                    )

                if kg_nodes:
                    kg.upsert_nodes(kg_nodes)
                    # Link hypotheses to a synthetic session topic for quick neighborhood traversal.
                    root_id = f"dream_session::{int(now_ts)}"
                    kg.upsert_nodes(
                        [
                            {
                                "id": root_id,
                                "type": "topic",
                                "label": "Dream Session",
                                "props": {"query": rule.query, "topic_hint": rule.topic_hint or ""},
                                "mtime": now_ts,
                            }
                        ]
                    )
                    for n in kg_nodes:
                        kg_edges.append(
                            {
                                "src": root_id,
                                "rel": "suggests",
                                "dst": str(n.get("id")),
                                "weight": 0.5,
                                "props": {"source": "dreams_engine"},
                                "mtime": now_ts,
                            }
                        )
                    if kg_edges:
                        kg.upsert_edges(kg_edges)
            except Exception:
                persisted_hyp = 0

        saved = int(rep.get("stored") and 1 or 0)
        if persisted_hyp > saved:
            saved = persisted_hyp

        return {
            "ok": bool(rep.get("ok")),
            "clusters": clusters,
            "hypotheses": hypotheses,
            "saved": saved,
            "warnings": [] if rep.get("ok") else [str(rep.get("error") or "dream_run_failed")],
            "iter18": rep,
        }


def run_dream(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(payload or {})
    text = str(payload.get("text") or "").strip()

    class _PayloadMM:
        def flashback(self, query: str = "*", k: int = 50) -> List[Dict[str, Any]]:
            if not text:
                return []
            return [{"id": "payload_1", "text": text, "mtime": float(time.time())}]

    engine = DreamsEngine(mm=_PayloadMM())
    rule = DreamRule(query=str(payload.get("query") or "*"))
    return engine.run([rule])


__all__ = ["DreamRule", "DreamsEngine", "DreamRunner", "run_dream"]
