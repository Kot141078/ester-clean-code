# -*- coding: utf-8 -*-
"""
rag_pipeline.py — izvlechenie i ranzhirovanie konteksta dlya RAG.

Glavnaya funktsiya:
    retrieve(query, *, k:int, mmr_lambda:float|None, filters:dict, max_ctx:int, store) -> dict

Vozvraschaet:
{
  "context_chunks": [
    { "id", "text", "doc_id", "page", "offset", "folder", "collection", "score" }
  ],
  "ranked": [
    { "id", "doc_id", "rank", "score", "sim", "div", "mmr", "meta": {...} }
  ],
  "stats": {
      "retrieval_ms", "total_tokens", "used_mmr",
      "candidates", "selected", "budget_left", "engine"
  }
}

Osobennosti:
- Filtry: collection, folder, doc_id.
- MMR (Maximal Marginal Relevance) — optsionalno.
  * Esli est numpy i mozhno dostat embeddings — ispolzuem kosinus.
  * Esli embeddings net — ispolzuem uproschennyy MMR po token-dzhakkardu (diversity) + base_score (sim).
  * Esli numpy net — myagko otkatyvaemsya na top-k.
- Obrezka konteksta po max_ctx (priblizitelnye tokeny: ~4 simvola na token).

Mosty:
- Yavnyy: VectorStore.search → ranked/context_chunks → prompt (kontekst kak artefakt dlya “roditelya”).
- Skrytye:
  1) Infoteoriya ↔ ekspluatatsiya: max_ctx i tokens — ogranichenie propusknoy sposobnosti kanala.
  2) Kibernetika ↔ nadezhnost: MMR optional → degradatsiya bez padeniya pri nedostayuschikh zavisimostyakh.

ZEMNOY ABZATs: v kontse fayla.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import numpy as _np  # dlya MMR
except Exception:
    _np = None


# --- Tokeny: legkaya approksimatsiya (bez zavisimostey) ---
def _approx_tokens(txt: str) -> int:
    if not txt:
        return 0
    # ~4 simvola na token (grubaya otsenka, soglasovana s Trace-praktikoy)
    return max(1, int(math.ceil(len(txt) / 4.0)))


def _meta_get(meta: Dict[str, Any], key: str, default: Any = None) -> Any:
    v = meta.get(key)
    return v if v is not None else default


def _coerce_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _normalize_scores(scores: List[float]) -> List[float]:
    if not scores:
        return []
    mx = max(scores)
    if mx <= 0:
        return [0.0 for _ in scores]
    # normiruem v [0..1]
    return [float(s) / (float(mx) + 1e-9) for s in scores]


def _token_set(txt: str) -> set:
    # ochen prostoy tokenayzer (bez regex, chtoby ne plodit zavisimostey)
    # rezhem po probelam, chistim punktuatsiyu krayami
    out = set()
    for w in (txt or "").lower().split():
        w = w.strip(".,;:!?()[]{}<>\"'`~|/\\")
        if len(w) >= 2:
            out.add(w)
    return out


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter <= 0:
        return 0.0
    union = len(a | b)
    return float(inter) / float(union + 1e-9)


def _filter_fn_factory(filters: Dict[str, Any]):
    want_collection = (filters or {}).get("collection")
    want_folder = (filters or {}).get("folder")
    want_doc_id = (filters or {}).get("doc_id")

    def _f(meta: Dict[str, Any], doc_id: str) -> bool:
        if want_collection is not None:
            if str(_meta_get(meta, "collection", "")).lower() != str(want_collection).lower():
                return False
        if want_folder is not None:
            if str(_meta_get(meta, "folder", "")).lower() != str(want_folder).lower():
                return False
        if want_doc_id is not None:
            if str(doc_id) != str(want_doc_id):
                return False
        return True

    return _f


def _store_iface(store: Any):
    """
    Unifitsiruem raznye realizatsii:

    Vozvraschaem:
      search(q, k, filter_fn)->List[(id,score)]
      get(id)->(text, meta)

    Podderzhivaem:
      - .search_with_trace(query, k, filter_fn=...)
      - .search(query, k, filter_fn=...)
      - .get(id) -> dict(text/metadata)
      - .to_dict()["docs"][id] -> dict(text/metadata/emb)
    """
    vs = store.vstore if hasattr(store, "vstore") else store

    def _get(doc_id: str) -> Tuple[str, Dict[str, Any]]:
        # 1) metod get()
        if hasattr(vs, "get"):
            try:
                d = vs.get(doc_id)
                if isinstance(d, dict):
                    text = d.get("text") or d.get("chunk") or ""
                    meta = d.get("metadata") or d.get("meta") or {}
                    return str(text), dict(meta) if isinstance(meta, dict) else {}
            except Exception:
                pass

        # 2) to_dict()
        try:
            dct = vs.to_dict()
            docs = dct.get("docs") or {}
            node = docs.get(doc_id) or {}
            text = node.get("text") or node.get("chunk") or ""
            meta = node.get("metadata") or node.get("meta") or {}
            return str(text), dict(meta) if isinstance(meta, dict) else {}
        except Exception:
            return "", {}

    def _coerce_search_res(res: Any) -> List[Tuple[str, float]]:
        if res is None:
            return []
        # ozhidaem List[(id, score)]
        if isinstance(res, list):
            out: List[Tuple[str, float]] = []
            for it in res:
                if isinstance(it, (list, tuple)) and len(it) >= 2:
                    out.append((str(it[0]), float(it[1])))
                elif isinstance(it, dict):
                    did = it.get("id") or it.get("doc_id")
                    sc = it.get("score") or it.get("sim") or 0.0
                    if did is not None:
                        out.append((str(did), float(sc)))
            return out
        return []

    def _search(query: str, top_k: int, filter_fn):
        # 1) search_with_trace
        if hasattr(vs, "search_with_trace"):
            try:
                res = vs.search_with_trace(query, top_k, filter_fn=filter_fn)
                # byvaet (res, trace) ili srazu res
                if isinstance(res, (list, tuple)) and len(res) == 2 and isinstance(res[0], list):
                    return _coerce_search_res(res[0])
                return _coerce_search_res(res)
            except Exception:
                pass

        # 2) search
        if hasattr(vs, "search"):
            try:
                res = vs.search(query, top_k, filter_fn=filter_fn)
                return _coerce_search_res(res)
            except Exception:
                pass

        # 3) fallback: perebor to_dict (TF-lite)
        try:
            dct = vs.to_dict()
            docs = dct.get("docs") or {}
        except Exception:
            docs = {}

        q_tokens = set((query or "").lower().split())
        scored: List[Tuple[str, float]] = []
        for did, node in docs.items():
            meta = node.get("metadata") or node.get("meta") or {}
            if filter_fn and not filter_fn(meta if isinstance(meta, dict) else {}, did):
                continue
            text = node.get("text") or node.get("chunk") or ""
            if not text:
                continue
            t_tokens = set(str(text).lower().split())
            inter = len(q_tokens & t_tokens)
            score = inter / (1 + len(t_tokens))
            if score > 0:
                scored.append((str(did), float(score)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    return _search, _get


def _try_vectors_for_mmr(store: Any, ids: List[str]):
    """
    Pytaemsya vytaschit embeddings kandidatov iz store.to_dict()["docs"][id]["emb"].
    Vozvraschaet: (query_vec, cand_vecs, ok)
      query_vec obychno otsutstvuet — vozvraschaem None.
    """
    try:
        vs = store.vstore if hasattr(store, "vstore") else store
        dct = vs.to_dict()
        docs = dct.get("docs") or {}
        vecs = []
        for did in ids:
            e = docs.get(did) or {}
            emb = e.get("emb")
            if isinstance(emb, list) and emb:
                vecs.append(emb)
            else:
                return None, None, False
        return None, vecs, True
    except Exception:
        return None, None, False


def _mmr_greedy(
    *,
    k: int,
    mmr_lambda: float,
    sim_qc: List[float],
    sim_cc: Optional[Any] = None,
    token_sets: Optional[List[set]] = None,
) -> Tuple[List[int], Dict[int, Dict[str, float]]]:
    """
    Greedy MMR.

    sim_qc: similarity(query, cand_i) in [0..1]
    sim_cc: matrix similarity(cand_i, cand_j) in [0..1] (optional)
    token_sets: alternative diversity source when sim_cc is None
    """
    N = len(sim_qc)
    if N <= 0 or k <= 0:
        return [], {}

    lam = float(mmr_lambda)
    lam = max(0.0, min(1.0, lam))

    selected: List[int] = []
    weights: Dict[int, Dict[str, float]] = {}

    # cache for jaccard
    jac_cache: Dict[Tuple[int, int], float] = {}

    def _div(i: int, j: int) -> float:
        # similarity between candidates (penalty if high)
        if sim_cc is not None:
            return float(sim_cc[i, j])
        if token_sets is None:
            return 0.0
        a, b = token_sets[i], token_sets[j]
        key = (i, j) if i <= j else (j, i)
        if key in jac_cache:
            return jac_cache[key]
        v = _jaccard(a, b)
        jac_cache[key] = v
        return v

    remaining = list(range(N))
    for _ in range(min(k, N)):
        best_i, best_mmr = -1, -1e9
        best_sim, best_div = 0.0, 0.0

        for i in remaining:
            max_sim_to_sel = 0.0
            if selected:
                for j in selected:
                    max_sim_to_sel = max(max_sim_to_sel, _div(i, j))
            mmr_val = lam * float(sim_qc[i]) - (1.0 - lam) * float(max_sim_to_sel)
            if mmr_val > best_mmr:
                best_i = i
                best_mmr = mmr_val
                best_sim = float(sim_qc[i])
                best_div = float(max_sim_to_sel)

        selected.append(best_i)
        remaining.remove(best_i)
        weights[best_i] = {"sim": best_sim, "div": best_div, "mmr": float(best_mmr)}

    return selected, weights


def retrieve(
    query: str,
    *,
    k: int,
    mmr_lambda: Optional[float],
    filters: Dict[str, Any],
    max_ctx: int,
    store: Any,
) -> Dict[str, Any]:
    t0 = time.time()

    k = max(1, int(k or 1))
    max_ctx = max(0, int(max_ctx or 0))

    search, get = _store_iface(store)
    ffn = _filter_fn_factory(filters or {})

    # Bazovyy poisk (berem zapas kandidatov, chtoby MMR bylo iz chego vybrat)
    base = search(query, max(8, k * 3), ffn)

    cand_ids: List[str] = [cid for cid, _ in base]
    cand_scores: List[float] = [float(s) for _, s in base]

    cand_texts: List[str] = []
    cand_metas: List[Dict[str, Any]] = []
    for cid in cand_ids:
        txt, meta = get(cid)
        cand_texts.append(txt or "")
        cand_metas.append(meta or {})

    used_mmr = False
    engine = "topk"
    selected_idx: List[int] = list(range(min(k, len(cand_ids))))
    weights_map: Dict[int, Dict[str, float]] = {}

    if (
        mmr_lambda is not None
        and _np is not None
        and len(cand_ids) > 0
        and k > 0
        and 0.0 <= float(mmr_lambda) <= 1.0
    ):
        # (A) try embeddings
        q_vec, c_vecs, ok = _try_vectors_for_mmr(store, cand_ids)
        if ok and c_vecs is not None:
            try:
                np = _np  # type: ignore
                C = np.array(c_vecs, dtype="float32")
                # normalize rows
                denom = (np.linalg.norm(C, axis=1, keepdims=True) + 1e-8)
                Cn = C / denom
                sim_cc = Cn @ Cn.T
                # query similarity: esli q_vec net — ispolzuem normirovannye base_scores
                sim_qc = _normalize_scores(cand_scores)
                selected_idx, weights_map = _mmr_greedy(
                    k=k, mmr_lambda=float(mmr_lambda), sim_qc=sim_qc, sim_cc=sim_cc
                )
                used_mmr = True
                engine = "mmr:emb"
            except Exception:
                used_mmr = False
                engine = "topk"

        # (B) token-jaccard MMR (kogda embeddings net, no numpy est)
        if not used_mmr:
            try:
                token_sets = [_token_set(t) for t in cand_texts]
                sim_qc = _normalize_scores(cand_scores)
                selected_idx, weights_map = _mmr_greedy(
                    k=k, mmr_lambda=float(mmr_lambda), sim_qc=sim_qc, sim_cc=None, token_sets=token_sets
                )
                used_mmr = True
                engine = "mmr:jaccard"
            except Exception:
                used_mmr = False
                engine = "topk"

    # Sobiraem vybrannye kuski i rezhem po max_ctx
    context_chunks: List[Dict[str, Any]] = []
    ranked: List[Dict[str, Any]] = []

    budget = int(max_ctx)
    for rank, i in enumerate(selected_idx):
        cid = cand_ids[i]
        text = cand_texts[i] or ""
        meta = cand_metas[i] or {}
        score = float(cand_scores[i])

        doc_id = str(meta.get("doc_id") or cid)
        page = _coerce_int(meta.get("page") or meta.get("sheet") or meta.get("slide") or 0, 0)
        offset = _coerce_int(meta.get("offset") or meta.get("chunk_index") or 0, 0)
        folder = str(_meta_get(meta, "folder", "") or "")
        collection = str(_meta_get(meta, "collection", "") or "")

        # byudzhet tokenov
        tks = _approx_tokens(text)
        if budget > 0 and tks > budget:
            max_chars = max(0, budget * 4)
            text = text[:max_chars]
            tks = _approx_tokens(text)
        if budget > 0:
            budget -= tks

        context_chunks.append(
            {
                "id": cid,
                "text": text,
                "doc_id": doc_id,
                "page": page,
                "offset": offset,
                "folder": folder,
                "collection": collection,
                "score": score,
            }
        )

        w = weights_map.get(i, {"sim": None, "div": None, "mmr": None})
        ranked.append(
            {
                "id": cid,
                "doc_id": doc_id,
                "rank": rank + 1,
                "score": score,
                "sim": w.get("sim"),
                "div": w.get("div"),
                "mmr": w.get("mmr"),
                "meta": {
                    "page": page,
                    "offset": offset,
                    "folder": folder,
                    "collection": collection,
                },
            }
        )

        if budget <= 0 and max_ctx > 0:
            break

    stats = {
        "retrieval_ms": (time.time() - t0) * 1000.0,
        "total_tokens": sum(_approx_tokens(c["text"]) for c in context_chunks),
        "used_mmr": bool(used_mmr),
        "candidates": int(len(cand_ids)),
        "selected": int(len(context_chunks)),
        "budget_left": int(max(0, budget)),
        "engine": engine,
    }

    return {"context_chunks": context_chunks, "ranked": ranked, "stats": stats}


__all__ = ["retrieve"]


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
RAG-payplayn — eto kak podgotovka instrumentov pered smenoy: ty beresh ne vse podryad so sklada,
a tolko to, chto vlezet v yaschik (max_ctx) i realno prigoditsya. MMR — eto “ne brat pyat odinakovykh klyuchey”:
pust luchshe budet odin klyuch, odna otvertka i odin tester, chem pyat klyuchey odnogo razmera.
"""