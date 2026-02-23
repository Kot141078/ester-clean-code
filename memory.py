# -*- coding: utf-8 -*-
"""
HumanMemory (v4)
Epizodicheskaya / Semanticheskaya / Kartochki.
- episodic: JSONL append-only v vstore/ester_memory.jsonl
- semantic: FAISS (cosine) + meta v JSONL; folbek — TF-IDF (scikit-learn)
- cards: JSONL (pin/listing)
- Avto-rotatsiya JSONL pri > rotate_threshold zapisey.
- recall(query, k, scopes=...) => obedinennaya vydacha so skoupom i score.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# sentence-transformers (lokalno) — po vozmozhnosti; inache folbek na TF-IDF
try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

# FAISS (CPU)
try:
    import faiss  # type: ignore
except Exception:
    faiss = None

# TF-IDF fallback
try:
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
    from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
except Exception:
    TfidfVectorizer, cosine_similarity = None, None


def _now_iso() -> str:
    import datetime as dt

    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()


def _norm(vec):
    import numpy as np

    v = vec.astype("float32")
    n = float((v**2).sum()) ** 0.5
    return v / (n + 1e-9)


class _SemanticIndex:
    """
    FAISS + JSONL meta; esli FAISS/encoder nedostupny — TF-IDF fallback.
    """

    def __init__(self, faiss_path: str, meta_jsonl: str, use_local_model: bool = True):
        self.faiss_path = faiss_path
        self.meta_jsonl = meta_jsonl
        self.use_local_model = use_local_model
        self.encoder = None
        self.dim = None
        self.index = None  # faiss.IndexIP
        self.meta: List[Dict[str, Any]] = []  # [{id, text, created_at, ...}]

        self._tfidf = None
        self._tfidf_texts: List[str] = []
        self._tfidf_meta: List[Dict[str, Any]] = []

        self._load()

    def _load(self):
        # meta
        if os.path.exists(self.meta_jsonl):
            with open(self.meta_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        self.meta.append(json.loads(line))
                    except Exception:
                        continue

        # encoder
        if SentenceTransformer is not None and self.use_local_model:
            try:
                self.encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                self.dim = int(self.encoder.get_sentence_embedding_dimension())
            except Exception:
                self.encoder = None

        # faiss
        if faiss is not None and self.encoder is not None and os.path.exists(self.faiss_path):
            try:
                self.index = faiss.read_index(self.faiss_path)
                self.dim = self.index.d  # type: ignore
            except Exception:
                self.index = None

        # tf-idf fallback
        if self.encoder is None or (faiss is None):
            if TfidfVectorizer is not None:
                self._rebuild_tfidf()

    def _rebuild_tfidf(self):
        if TfidfVectorizer is None:
            return
        texts = [m.get("text", "") for m in self.meta]
        self._tfidf_texts = texts
        self._tfidf_meta = self.meta[:]
        if texts:
            self._tfidf = TfidfVectorizer(max_features=20000).fit(texts)

    def _persist_meta_line(self, rec: Dict[str, Any]):
        with open(self.meta_jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _persist_faiss(self):
        if self.index is not None:
            faiss.write_index(self.index, self.faiss_path)

    def add(self, rec_id: str, text: str, extra: Dict[str, Any]):
        # meta
        meta = {"id": rec_id, "text": text, **extra}
        self.meta.append(meta)
        self._persist_meta_line(meta)

        # faiss or tf-idf
        if self.encoder is not None and faiss is not None:
            import numpy as np

            vec = self.encoder.encode([text])
            v = _norm(np.array(vec, dtype="float32"))
            if self.index is None:
                self.index = faiss.IndexFlatIP(
                    v.shape[1]
                )  # cosine via inner product over normalized vectors
            self.index.add(v)
            self._persist_faiss()
        else:
            self._rebuild_tfidf()

    def search(self, query: str, k: int = 8) -> List[Tuple[str, float, Dict[str, Any]]]:
        if not query.strip():
            return []
        if (
            self.encoder is not None
            and faiss is not None
            and self.index is not None
            and len(self.meta) > 0
        ):
            import numpy as np

            qv = _norm(np.array(self.encoder.encode([query]), dtype="float32"))
            scores, idx = self.index.search(qv, k)
            out: List[Tuple[str, float, Dict[str, Any]]] = []
            for i, sc in zip(idx[0].tolist(), scores[0].tolist()):
                if i < 0 or i >= len(self.meta):
                    continue
                m = self.meta[i]
                out.append((m["id"], float(sc), m))
            return out
        # TF-IDF fallback
        if self._tfidf is None or not self._tfidf_texts:
            return []
        q = self._tfidf.transform([query])
        X = self._tfidf.transform(self._tfidf_texts)
        import numpy as np

        sims = cosine_similarity(q, X)[0]  # type: ignore
        idxs = np.argsort(-sims)[:k]
        out = []
        for i in idxs:
            m = self._tfidf_meta[int(i)]
            out.append((m["id"], float(sims[int(i)]), m))
        return out


class HumanMemory:
    def __init__(
        self,
        episodic_path: str,
        faiss_path: str,
        semantic_meta_path: str,
        cards_path: str,
        rotate_threshold: int = 10000,
    ):
        self.episodic_path = episodic_path
        self.semantic = _SemanticIndex(faiss_path, semantic_meta_path, use_local_model=True)
        self.cards_path = cards_path
        self.rotate_threshold = rotate_threshold

        for p in (
            os.path.dirname(episodic_path),
            os.path.dirname(faiss_path),
            os.path.dirname(cards_path),
        ):
            if p:
                os.makedirs(p, exist_ok=True)

        # lazy counters
        self._line_count_cache = None

    # ---------- helpers ----------
    def _append_jsonl(self, path: str, obj: Dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def _count_lines(self, path: str) -> int:
        if not os.path.exists(path):
            return 0
        cnt = 0
        with open(path, "r", encoding="utf-8") as f:
            for _ in f:
                cnt += 1
        return cnt

    def _rotate_if_needed(self, path: str) -> None:
        try:
            n = self._count_lines(path)
            if n > self.rotate_threshold:
                base, ext = os.path.splitext(path)
                ts = int(time.time())
                newp = f"{base}.{ts}.jsonl"
                os.replace(path, newp)
        except Exception:
            pass

    def _new_id(self, prefix: str = "M") -> str:
        return f"{prefix}{uuid.uuid4().hex[:8]}"

    # ---------- public API ----------
    def remember(
        self,
        text: str,
        *,
        tags: List[str] = [],
        aliases: List[str] = [],
        source_ref: Optional[str] = None,
        ttl_days: Optional[int] = None,
    ) -> str:
        rec_id = self._new_id("M")
        rec = {
            "id": rec_id,
            "text": text,
            "tags": tags,
            "aliases": aliases,
            "source_ref": source_ref,
            "ttl_days": ttl_days,
            "scope": "episodic",
            "created_at": _now_iso(),
        }
        self._append_jsonl(self.episodic_path, rec)
        self._rotate_if_needed(self.episodic_path)
        # indeksiruem v semantike, chtoby recall rabotal dazhe dlya epizodiki
        self.semantic.add(
            rec_id, text, {"created_at": rec["created_at"], "scope": "semantic-shadow"}
        )
        return rec_id

    def recall(
        self,
        query: str,
        *,
        k: int = 8,
        scopes: List[str] = ["episodic", "semantic", "cards"],
    ) -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        out: List[Dict[str, Any]] = []

        # semantic
        if "semantic" in scopes:
            sem_hits = self.semantic.search(query, k=k)
            for mid, sc, meta in sem_hits:
                out.append(
                    {
                        "id": mid,
                        "text": meta.get("text", ""),
                        "score": float(sc),
                        "scope": "semantic",
                        "created_at": meta.get("created_at"),
                        "aliases": meta.get("aliases", []),
                        "source_ref": meta.get("source_ref"),
                        "tags": meta.get("tags", []),
                    }
                )

        # episodic (prostaya TF-IDF po faylu)
        if "episodic" in scopes:
            epi = self._search_episodic_tfidf(query, top=k)
            out.extend(
                [
                    {
                        "id": r["id"],
                        "text": r["text"],
                        "score": r["score"],
                        "scope": "episodic",
                        "created_at": r.get("created_at"),
                        "aliases": r.get("aliases", []),
                        "source_ref": r.get("source_ref"),
                        "tags": r.get("tags", []),
                    }
                    for r in epi
                ]
            )

        # cards (filtratsiya po podstroke + prostaya relevantnost)
        if "cards" in scopes:
            cards = self._search_cards(query, top=k)
            out.extend(
                [
                    {
                        "id": c["id"],
                        "text": c["text"],
                        "score": c["score"],
                        "scope": "cards",
                        "created_at": c.get("created_at"),
                        "aliases": c.get("aliases", []),
                        "source_ref": c.get("source_ref"),
                        "tags": c.get("tags", []),
                    }
                    for c in cards
                ]
            )

        # obedinennaya sortirovka po score (desc)
        out.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return out[:k]

    def pin(
        self,
        text: str,
        *,
        source_ref: Optional[str] = None,
        aliases: List[str] = [],
        tags: List[str] = [],
    ) -> str:
        card_id = self._new_id("C")
        rec = {
            "id": card_id,
            "text": text,
            "tags": tags,
            "aliases": aliases,
            "source_ref": source_ref,
            "created_at": _now_iso(),
        }
        self._append_jsonl(self.cards_path, rec)
        self._rotate_if_needed(self.cards_path)
        # indeksatsiya v semantike dlya recall
        self.semantic.add(card_id, text, {"created_at": rec["created_at"], "scope": "cards"})
        return card_id

    def cards_list(
        self,
        *,
        q: str = "",
        tag: Optional[str] = None,
        alias: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        items: List[Dict[str, Any]] = []
        if os.path.exists(self.cards_path):
            with open(self.cards_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        items.append(obj)
                    except Exception:
                        continue
        items2 = []
        ql = (q or "").lower()
        for it in items:
            if ql and ql not in it.get("text", "").lower():
                continue
            if tag and tag not in it.get("tags", []):
                continue
            if alias and alias not in it.get("aliases", []):
                continue
            items2.append(it)
        total = len(items2)
        start = max(0, (page - 1) * page_size)
        end = start + page_size
        return items2[start:end], total

    # ---------- internals ----------
    def _search_episodic_tfidf(self, query: str, top: int = 8) -> List[Dict[str, Any]]:
        # chitaem ves JSONL (prostaya strategiya; dlya bolshikh obemov — derzhat kesh/indeks)
        rows: List[Dict[str, Any]] = []
        if os.path.exists(self.episodic_path):
            with open(self.episodic_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
        if not rows or TfidfVectorizer is None:
            return []
        texts = [r.get("text", "") for r in rows]
        vec = TfidfVectorizer(max_features=20000)
        X = vec.fit_transform(texts)
        q = vec.transform([query])
        import numpy as np

        sims = (q @ X.T).toarray()[0]
        idxs = np.argsort(-sims)[:top]
        out: List[Dict[str, Any]] = []
        for i in idxs:
            r = rows[int(i)]
            out.append(
                {
                    "id": r.get("id"),
                    "text": r.get("text", ""),
                    "score": float(sims[int(i)]),
                    "created_at": r.get("created_at"),
                    "aliases": r.get("aliases", []),
                    "source_ref": r.get("source_ref"),
                    "tags": r.get("tags", []),
                }
            )
        return out

    def _search_cards(self, query: str, top: int = 8) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if os.path.exists(self.cards_path):
            with open(self.cards_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
        if not rows:
            return []
        ql = query.lower().strip()
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for r in rows:
            t = r.get("text", "")
            score = 0.0
            if ql:
                score = float(t.lower().count(ql)) + (1.0 if ql in t.lower() else 0.0)
            scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": r["id"],
                "text": r.get("text", ""),
                "score": float(s),
                "created_at": r.get("created_at"),
                "aliases": r.get("aliases", []),
                "source_ref": r.get("source_ref"),
                "tags": r.get("tags", []),
            }
            for s, r in scored[:top]
        ]
