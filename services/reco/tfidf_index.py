# -*- coding: utf-8 -*-
"""
R3/services/reco/tfidf_index.py — indeks TF-IDF nad kartochkami Ester (CardsMemory).

Mosty:
- Yavnyy: Cover & Thomas — TF-IDF povyshaet poleznyy signal i ponizhaet izbytochnost cherez IDF.
- Skrytyy #1: Enderton — model kak kompozitsiya predikatov (tf, df, idf, kosinus), vse proveryaemo i vosproizvodimo.
- Skrytyy #2: Ashbi — A/B-slot cherez R3_MODE (A=unigrammy; B=unigrammy+bigrammy+bonus svezhesti), s avtokatbekom v A.

Zemnoy abzats:
Indeks stroitsya tolko na stdlib i khranitsya v JSON (sparse dict), sovmestim s maloy pamyatyu.
Chitaet kartochki cherez mm_access (esli dostupno), inache — napryamuyu `PERSIST_DIR/ester_cards.json`.
Podderzhivaet limit `R3_MAX_DOCS`, sokhranenie v `data/reco/*`, skoring kosinusom.

# c=a+b
"""
from __future__ import annotations
import json
import math
import os
import time
from typing import Dict, List, Tuple

from services.reco.tokenizer import tokenize  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Puti khraneniya indeksa
def _paths():
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    reco = os.path.join(base, "reco")
    os.makedirs(reco, exist_ok=True)
    return (
        os.path.join(reco, "tfidf_vocab.json"),
        os.path.join(reco, "tfidf_docs.json"),
        os.path.join(reco, "tfidf_meta.json"),
    )

def _load_cards() -> List[Dict]:
    # 1) Pytaemsya cherez MemoryManager
    try:
        from services.mm_access import get_mm  # type: ignore
        mm = get_mm()
        # probuem nabor izvestnykh metodov
        for m in ("iter_cards", "list_cards", "all_cards"):
            if hasattr(mm.cards, m):
                cards = list(getattr(mm.cards, m)())
                if cards:
                    return cards
        # poslednyaya popytka — poluchit "syrye" struktury
        if hasattr(mm.cards, "to_list"):
            return list(mm.cards.to_list())
    except Exception:
        pass
    # 2) Folbek: chitaem JSON napryamuyu
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    path = os.path.join(base, "ester_cards.json")
    if not os.path.isfile(path):
        return []
    try:
        raw = json.load(open(path, "r", encoding="utf-8"))
        # dopuskaem dva formata: spisok; libo dict s klyuchom "cards"
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict) and "cards" in raw:
            return list(raw["cards"])
    except Exception:
        return []
    return []

def _get_text(card: Dict) -> str:
    for k in ("text", "content", "body"):
        if k in card and isinstance(card[k], str):
            return card[k]
    return ""

def _get_user(card: Dict) -> str:
    for k in ("user", "owner", "author", "created_by"):
        v = card.get(k)
        if isinstance(v, str):
            return v
    return "unknown"

def _get_tags(card: Dict) -> List[str]:
    v = card.get("tags") or []
    if isinstance(v, list):
        return [str(x) for x in v]
    if isinstance(v, str):
        return [v]
    return []

def _get_ts(card: Dict) -> float:
    for k in ("ts", "timestamp", "created_at", "time"):
        v = card.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            # try parse epoch as string
            try:
                return float(v)
            except Exception:
                pass
    return 0.0

class TfidfIndex:
    def __init__(self):
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.docs: List[Dict] = []  # [{ "vec": {term: tfidf, ...}, "len": float, "meta": {...}}]

    # -------- indeksatsiya --------
    def fit(self, cards: List[Dict]) -> int:
        max_docs = int(os.getenv("R3_MAX_DOCS", "50000"))
        docs = []
        df: Dict[str, int] = {}
        # soberem syrye tf
        for i, c in enumerate(cards[:max_docs]):
            text = _get_text(c)
            if not text:
                continue
            toks = tokenize(text)
            if not toks:
                continue
            tf: Dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            docs.append((tf, c))
            for t in set(tf.keys()):
                df[t] = df.get(t, 0) + 1

        # slovar i idf
        terms = sorted(df.keys())
        self.vocab = {t: i for i, t in enumerate(terms)}
        N = max(1, len(docs))
        self.idf = {t: math.log((N + 1) / (df[t] + 1)) + 1.0 for t in terms}

        # tf-idf vektora
        self.docs = []
        now = time.time()
        for tf, c in docs:
            vec: Dict[str, float] = {}
            for t, cnt in tf.items():
                if t not in self.idf:
                    continue
                w = (cnt / max(1.0, sum(tf.values()))) * self.idf[t]
                vec[t] = w
            # dlina
            l2 = math.sqrt(sum(v * v for v in vec.values())) or 1.0

            # bonus za svezhest (rezhim B)
            if (os.getenv("R3_MODE") or "A").strip().upper() == "B":
                try:
                    age_days = max(0.0, (now - _get_ts(c)) / 86400.0) if _get_ts(c) > 0 else 365.0
                    boost = 1.0 + max(0.0, (30.0 - min(30.0, age_days))) / 100.0  # do +30% za noviznu
                    l2 *= 1.0 / boost  # ekvivalent normalizatsii povyshayuschey vklad novizny
                except Exception:
                    pass  # avtokatbek: ignoriruem bonus

            self.docs.append({
                "vec": vec,
                "len": l2,
                "meta": {
                    "user": _get_user(c),
                    "tags": _get_tags(c),
                    "ts": _get_ts(c),
                    "snippet": (_get_text(c)[:200] + ("…" if len(_get_text(c)) > 200 else "")),
                }
            })
        return len(self.docs)

    # -------- sokhranenie/zagruzka --------
    def save(self) -> None:
        p_vocab, p_docs, p_meta = _paths()
        with open(p_vocab, "w", encoding="utf-8") as f:
            json.dump({"vocab": self.vocab, "idf": self.idf}, f, ensure_ascii=False)
        with open(p_docs, "w", encoding="utf-8") as f:
            json.dump(self.docs, f, ensure_ascii=False)

    def load(self) -> bool:
        p_vocab, p_docs, _ = _paths()
        if not (os.path.isfile(p_vocab) and os.path.isfile(p_docs)):
            return False
        data = json.load(open(p_vocab, "r", encoding="utf-8"))
        self.vocab = data.get("vocab") or {}
        self.idf = data.get("idf") or {}
        self.docs = json.load(open(p_docs, "r", encoding="utf-8"))
        return True

    # -------- skoring --------
    def _vec_from_query(self, query: str) -> Tuple[Dict[str, float], float]:
        toks = tokenize(query)
        tf: Dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        vec: Dict[str, float] = {}
        total = max(1.0, sum(tf.values()))
        for t, cnt in tf.items():
            if t not in self.idf:
                continue
            vec[t] = (cnt / total) * self.idf[t]
        l2 = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return vec, l2

    def score(self, query: str, top: int = 10, tags_include: List[str] | None = None) -> List[Dict]:
        if not self.docs:
            loaded = self.load()
            if not loaded:
                return []
        qv, qlen = self._vec_from_query(query)
        if not qv:
            return []
        res: List[Tuple[float, int]] = []
        for i, d in enumerate(self.docs):
            if tags_include:
                doc_tags = set(d.get("meta", {}).get("tags") or [])
                if not set(tags_include) & doc_tags:
                    continue
            # kosinus
            dot = 0.0
            vec = d["vec"]
            for t, w in qv.items():
                if t in vec:
                    dot += w * vec[t]
            score = dot / (qlen * (d["len"] or 1.0))
            if score > 0:
                res.append((score, i))
        res.sort(key=lambda x: x[0], reverse=True)
        out = []
        for s, i in res[:max(1, int(top))]:
            meta = self.docs[i]["meta"]
            out.append({"score": round(float(s), 6), "idx": i, "meta": meta})
        return out

def build_index() -> int:
    cards = _load_cards()
    idx = TfidfIndex()
    n = idx.fit(cards)
    idx.save()
    return n