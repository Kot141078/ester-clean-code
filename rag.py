# -*- coding: utf-8 -*-
from __future__ import annotations

"""RAG-modul Ester: izvlechenie iz VectorStore, MMR-diversifikatsiya, sbor konteksta i tsitat.
Rabotaet v gibridnom rezhime: Sentence-Transformers (osnovnoy) or TF-IDF (folbek).

Yavnyy most: Ashby / requisite variety → MMR umenshaet “odnoobrazie” konteksta, povyshaya ustoychivost otveta.
(Nenazvannye mosty): mutual information (Cover&Thomas) kak intuitsiya pro izbytochnost; max-entropy (Jaynes) kak intuitsiya pro balans.

Zemnoy abzats (anatomiya/inzheneriya):
Esli kormit mozg tolko “odnoy arteriey” (odnim blizkim k zaprosu kuskom), on stanovitsya khrupkim: tromb/shum - i vse.
MMR - eto kak kollaterali: chut khuzhe po pryamoy “skorosti”, no luchshe po zhivuchesti i ustoychivosti k provalam/iskazheniyam."""

import os
import time
import logging
import inspect
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Trying to import VectorStore
try:
    from vector_store import VectorStore
except ImportError:  # pragma: no cover
    class VectorStore:  # type: ignore
        pass


# Import ML bibliotek
try:
    from sentence_transformers import SentenceTransformer, util as st_util  # type: ignore
    _HAS_ST = True
except Exception:
    _HAS_ST = False

# Folbeki (importiruem lenivo/akkuratno)
try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None  # type: ignore


_EMBEDDER: Optional["SentenceTransformer"] = None


def _cos_sim(a, b) -> float:
    if _HAS_ST:
        try:
            return float(st_util.cos_sim(a, b).item())
        except Exception:
            return 0.0

    # Fullback on numpas (if any)
    if np is None:
        return 0.0
    try:
        a = a.reshape(1, -1)
        b = b.reshape(1, -1)
        return float((a @ b.T).ravel()[0])
    except Exception:
        return 0.0


def _get_embedder() -> Optional["SentenceTransformer"]:
    """Lazy loading modeli (kesh)."""
    global _EMBEDDER
    if not _HAS_ST:
        return None
    if _EMBEDDER is not None:
        return _EMBEDDER

    model_name = os.environ.get("ESTER_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    try:
        _EMBEDDER = SentenceTransformer(model_name)
    except Exception as e:
        logging.warning(f"YuRAGSH Failed to load SentenceTransformer ъЗЗФ0ЗЗь: ЗЗФ1ЗЗ")
        _EMBEDDER = None
    return _EMBEDDER


def _embed(texts: List[str]):
    """Vozvraschaet matritsu embeddingov shape=(len(texts), dim).
    ST: encode(..., normalize_embeddings=True)
    TF-IDF: fit_transform + normalize
    Esli voobsche net zavisimostey - nulli."""
    model = _get_embedder()
    if model is not None:
        try:
            return model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        except Exception as e:
            logging.warning(f"[RAG] ST encode upal, pereklyuchayus na folbek: {e}")

    # TF-IDF Fallback
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        from sklearn.preprocessing import normalize  # type: ignore
        vec = TfidfVectorizer(min_df=1, max_df=0.95, ngram_range=(1, 2))
        X = vec.fit_transform(texts)
        X = normalize(X)
        return X.toarray()
    except Exception as e:
        logging.warning(f"[RAG] TF-IDF folbek nedostupen/upal: {e}")

    # Posledniy folbek: nuli
    if np is None:
        # sovsem grustno — khotya by spisok spiskov
        return [[0.0] * 10 for _ in texts]
    return np.zeros((len(texts), 10), dtype=float)


def _mmr(query_vec, cand_vecs, k: int, lambda_div: float = 0.5) -> List[int]:
    """Maximum Marginal Relevance.
    Predpolagaem, chto vektory uzhe normalizovany → dot ≈ cos."""
    if np is None:
        # Bez numpy MMR bessmyslenen — vernem pervye k
        return list(range(min(k, len(cand_vecs))))

    n = int(cand_vecs.shape[0]) if hasattr(cand_vecs, "shape") else 0
    if n <= 0:
        return []

    k = max(1, int(k))
    lambda_div = float(lambda_div)
    lambda_div = 0.0 if lambda_div < 0.0 else (1.0 if lambda_div > 1.0 else lambda_div)

    selected: List[int] = []
    candidates = list(range(n))

    q = query_vec.reshape(-1) if hasattr(query_vec, "reshape") else query_vec
    q = q if hasattr(q, "ndim") and q.ndim == 1 else np.array(q).reshape(-1)

    # sim_to_query: (n,)
    sim_to_query = (cand_vecs @ q.reshape(-1, 1)).ravel()

    first = int(np.argmax(sim_to_query))
    selected.append(first)
    candidates.remove(first)

    while len(selected) < min(k, n) and candidates:
        best_score = -1e18
        best_idx = candidates[0]

        for idx in candidates:
            # maximum similarity with already selected
            sim_to_selected = max(float(cand_vecs[idx] @ cand_vecs[j]) for j in selected)
            score = lambda_div * float(sim_to_query[idx]) - (1.0 - lambda_div) * sim_to_selected
            if score > best_score:
                best_score = score
                best_idx = idx

        selected.append(best_idx)
        candidates.remove(best_idx)

    return selected


def _format_locator(meta: Dict[str, Any]) -> str:
    """Formatting locator/source link (page/slide/sheet/section)."""
    if not meta:
        return ""
    locators = {
        "page": "p.",
        "slide": "slide",
        "sheet": "sheet",
        "section_index": "sec",
    }
    for key, prefix in locators.items():
        val = meta.get(key)
        if val is not None:
            return f"{prefix} {val}"
    # zapasnoy variant
    src = meta.get("source") or meta.get("file") or meta.get("path") or "unknown"
    return str(src)


def _estimate_tokens(text: str) -> int:
    """Rough valuation of tokens without external tokenizers.
    For RU/EN, on average 1 token ~ 3.5–4.0 characters."""
    if not text:
        return 0
    return max(1, int(len(text) / 3.8))


def _normalize_hit(hit: Any) -> Optional[Dict[str, Any]]:
    """
    Privodit raznye formaty rezultata poiska k edinomu vidu:
    {text, meta, score}
    """
    if hit is None:
        return None

    # Chastye formy: dict, (doc, score), doc-obekt
    if isinstance(hit, tuple) and len(hit) == 2:
        doc, score = hit
        meta = getattr(doc, "metadata", None) or {}
        text = getattr(doc, "page_content", None) or getattr(doc, "content", None) or str(doc)
        return {"text": text or "", "meta": meta or {}, "score": float(score) if score is not None else None}

    if isinstance(hit, dict):
        meta = hit.get("metadata") or hit.get("meta") or {}
        text = hit.get("text") or hit.get("content") or hit.get("page_content") or hit.get("chunk") or ""
        score = hit.get("score")
        if score is None and "distance" in hit:
            # distance is less → better. Convert to pseudo-score
            try:
                score = 1.0 - float(hit["distance"])
            except Exception:
                score = None
        return {"text": str(text) if text is not None else "", "meta": dict(meta) if meta else {}, "score": score}

    # doc-like
    text = getattr(hit, "page_content", None) or getattr(hit, "content", None)
    meta = getattr(hit, "metadata", None) or {}
    if text is not None:
        return {"text": str(text), "meta": dict(meta) if meta else {}, "score": None}

    return None


def _store_search(store: Any, query: str, top_n: int) -> List[Dict[str, Any]]:
    """Tries to pull VectorStore in different ways, without knowing its exact API.
    Returns a list of normalized thread dictionaries."""
    if store is None:
        return []

    methods = [
        "search",
        "query",
        "similarity_search_with_score",
        "similarity_search",
        "find",
    ]

    raw: Any = None
    for m in methods:
        if not hasattr(store, m):
            continue
        fn = getattr(store, m)
        try:
            sig = inspect.signature(fn)
            kwargs = {}
            # Podbiraem imya parametra top-k
            for kname in ("k", "top_k", "topn", "top_n", "limit", "n_results"):
                if kname in sig.parameters:
                    kwargs[kname] = int(top_n)
                    break
            # Selecting the name of the request parameter
            # Obychno query / text / q
            if "query" in sig.parameters:
                raw = fn(query=query, **kwargs)
            elif "text" in sig.parameters:
                raw = fn(text=query, **kwargs)
            elif "q" in sig.parameters:
                raw = fn(q=query, **kwargs)
            else:
                # pozitsionno
                raw = fn(query, **kwargs) if kwargs else fn(query)
            break
        except Exception as e:
            logging.warning(f"[RAG] VectorStore.{m} upal: {e}")
            raw = None

    # Normalizuem
    hits: List[Dict[str, Any]] = []
    if raw is None:
        return hits

    # equal can be leaf/dist with list
    if isinstance(raw, dict):
        # varianty: {"results": [...]}, {"documents": [...]}, {"matches": [...]}
        for key in ("results", "matches", "documents", "items"):
            if key in raw and isinstance(raw[key], list):
                raw = raw[key]
                break

    if isinstance(raw, list):
        for h in raw:
            nh = _normalize_hit(h)
            if nh and nh.get("text"):
                hits.append(nh)
    else:
        nh = _normalize_hit(raw)
        if nh and nh.get("text"):
            hits.append(nh)

    return hits


def _get_store() -> Optional[Any]:
    """Lazy creation of VectorStore.
    If your VectorStore needs a path/config, you can get it here via env."""
    try:
        # If the constructor has no arguments, great.
        return VectorStore()  # type: ignore
    except Exception:
        return None


async def collect_context(
    query: str,
    k: int = 5,
    max_context_tokens: int = 2000,
    store: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Osnovnoy metod RAG.
    Vozvraschaet spisok fragmentov:
      [
        {"text": "...", "citation": "[source | p. 3]", "meta": {...}, "score": 0.81, "rank": 1},
        ...
      ]
    """
    t0 = time.time()
    query = (query or "").strip()
    if not query:
        return []

    logging.info(f"yURAGSH Context request: ЗЗФ0З")

    k = max(1, int(k))
    max_context_tokens = max(200, int(max_context_tokens))

    store = store if store is not None else _get_store()
    top_n = int(os.environ.get("ESTER_RAG_TOPN", str(max(20, k * 5))))
    lambda_div = float(os.environ.get("ESTER_RAG_LAMBDA", "0.55"))

    hits = _store_search(store, query, top_n)
    if not hits:
        logging.info("[RAG] VectorStore vernul 0 kandidatov.")
        return []

    cand_texts = [h["text"] for h in hits]
    # embedim (query + candidates)
    vecs = _embed([query] + cand_texts)
    try:
        query_vec = vecs[0]
        cand_vecs = vecs[1:]
    except Exception:
        # if _embed returned lists
        query_vec = vecs[0]
        cand_vecs = vecs[1:]

    mmr_idx = _mmr(query_vec, cand_vecs, k=k, lambda_div=lambda_div)

    # Collecting the answer while respecting the budget
    out: List[Dict[str, Any]] = []
    used = 0
    rank = 0

    for idx in mmr_idx:
        if idx < 0 or idx >= len(hits):
            continue
        h = hits[idx]
        text = (h.get("text") or "").strip()
        if not text:
            continue

        meta = h.get("meta") or {}
        locator = _format_locator(meta)
        source = meta.get("source") or meta.get("file") or meta.get("path") or "unknown"
        citation = f"[{source} | {locator}]" if locator else f"[{source}]"

        cost = _estimate_tokens(text)
        if used + cost > max_context_tokens:
            # we get it partially (softly)
            remaining = max_context_tokens - used
            if remaining < 50:
                break
            # very rough: cut by symbols
            approx_chars = int(remaining * 3.8)
            text = text[:max(0, approx_chars)].rstrip() + "…"
            cost = _estimate_tokens(text)

        used += cost
        rank += 1
        out.append(
            {
                "text": text,
                "citation": citation,
                "meta": meta,
                "score": h.get("score"),
                "rank": rank,
            }
        )
        if len(out) >= k or used >= max_context_tokens:
            break

    dt = (time.time() - t0) * 1000.0
    logging.info(f"[RAG] Gotovo: chunks={len(out)} budget={used}/{max_context_tokens} dt_ms={dt:.1f}")
    return out