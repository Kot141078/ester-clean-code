# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Retrieval Router: doc_summary -> doc_chunks(MMR) -> structured flashback -> cards TF-IDF.
Returns context + provenance.
"""
import json
import math
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from modules.memory import store
from modules.memory.facade import memory_add
from modules.memory.vector import embed, cosine
try:
    from modules.memory.doc_lookup import build_doc_context as _build_doc_context  # type: ignore
    from modules.memory.doc_lookup import resolve_doc_for_query as _resolve_doc_for_query  # type: ignore
except Exception:
    _build_doc_context = None  # type: ignore
    _resolve_doc_for_query = None  # type: ignore

try:
    from modules.rag.hybrid import _tok as _tok_hybrid  # type: ignore
except Exception:
    _tok_hybrid = None  # type: ignore


DOC_QUERY_RE = re.compile(
    r"(?is)\b("
    r"doc|docs|document|documentation|readme|spec|specification|manual|guide|report|protocol|log|"
    r"pdf|docx|txt|md|html|page|citation|source|quoted|offset|"
    r"документ|доки|документация|спека|спецификац|мануал|руководство|отчет|протокол|лог|"
    r"файл|страниц|цитат|источник|ссылка|смещени|смещение"
    r")\b"
)

_INTERNAL_SIGNAL_SOURCES = {
    "analyst",
    "autoload",
    "companion",
    "discovery_loader",
    "dream",
    "initiative_engine",
    "modules.proactivity.planner_v1",
    "passport",
    "planner_v1",
    "proactivity",
    "volition",
}

_INTERNAL_SIGNAL_TEXT_MARKERS = (
    "planner_v1:",
    "initiative candidate:",
    "dream initiative:",
    "[dream_",
    "[volition_",
    "[discovery_",
    "[analyst_",
    "[passport_",
    "[tg_",
    "[autoload_",
    "[brain]",
    "[companion]",
    "[core]",
    "[hive]",
    "[initiative_autostart]",
    "[register_all_ok]",
    "[safe_chat]",
)


def is_doc_query(text: str) -> bool:
    try:
        return bool(DOC_QUERY_RE.search(text or ""))
    except Exception:
        return False


def _norm_path(p: str) -> str:
    try:
        return os.path.normpath(p)
    except Exception:
        return p or ""


def _parse_citation_page(cite: str) -> Optional[int]:
    if not cite:
        return None


def _normalize_signal_text(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def _looks_machine_event(text: str) -> bool:
    cleaned = _normalize_signal_text(text)
    if not cleaned.startswith("["):
        return False
    end = cleaned.find("]")
    if end <= 1:
        return False
    head = cleaned[1:end]
    normalized = re.sub(r"[^A-Za-z0-9_:-]+", "", head)
    if not normalized:
        return False
    letters = re.sub(r"[^A-Za-z]+", "", normalized)
    return bool(letters) and letters.upper() == letters


def _is_internal_signal_text(text: str) -> bool:
    cleaned = _normalize_signal_text(text)
    if not cleaned:
        return False
    low = cleaned.lower()
    if any(low.startswith(marker) for marker in _INTERNAL_SIGNAL_TEXT_MARKERS):
        return True
    return _looks_machine_event(cleaned)


def _is_internal_flashback_record(row: Dict[str, Any]) -> bool:
    src = dict(row or {})
    meta = src.get("meta") if isinstance(src.get("meta"), dict) else {}
    text = str(src.get("text") or "").strip()
    source_values = {
        str(meta.get("source") or "").strip().lower(),
        str(meta.get("type") or "").strip().lower(),
    }
    scope = str(meta.get("scope") or "").strip().lower()
    kind = str(src.get("type") or src.get("kind") or "").strip().lower()
    if scope == "internal":
        return True
    if any(value in _INTERNAL_SIGNAL_SOURCES for value in source_values if value):
        return True
    if _is_internal_signal_text(text):
        return True
    if kind in {"event", "trace"} and _looks_machine_event(text):
        return True
    return False


def _scope_flashback_records(
    rows: List[Dict[str, Any]],
    *,
    chat_id: Optional[int],
    user_id: Optional[int],
) -> Tuple[List[Dict[str, Any]], int]:
    base = [dict(r) for r in rows if isinstance(r, dict) and not _is_internal_flashback_record(r)]
    filtered_out = max(0, len(rows) - len(base))
    if chat_id is None and user_id is None:
        return base, filtered_out

    scoped: List[Dict[str, Any]] = []
    for r in base:
        meta = r.get("meta") if isinstance(r.get("meta"), dict) else {}
        if chat_id is not None and str(meta.get("chat_id") or "") not in ("", str(chat_id)):
            continue
        if user_id is not None and str(meta.get("user_id") or "") not in ("", str(user_id)):
            continue
        scoped.append(r)
    return (scoped if scoped else base), filtered_out
    m = re.search(r"\bp\.\s*(\d+)\b", cite)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _collect_records_by_type(types: List[str]) -> List[Dict[str, Any]]:
    types_l = {str(t or "").lower() for t in (types or [])}
    out: List[Dict[str, Any]] = []
    try:
        for r in list(getattr(store, "_MEM", {}).values()):
            if not isinstance(r, dict):
                continue
            tp = str(r.get("type") or r.get("kind") or "").lower()
            if tp in types_l:
                out.append(r)
    except Exception:
        pass
    return out


def _vector_rank(query: str, records: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    if not query or not records:
        return []
    qv = embed(query)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for r in records:
        v = r.get("vec") or []
        if not isinstance(v, list) or not v:
            continue
        try:
            s = cosine(qv, v, len(v))
        except Exception:
            continue
        scored.append((s, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[Dict[str, Any]] = []
    for s, r in scored[: max(1, int(top_k))]:
        rr = dict(r)
        rr["_score"] = float(s)
        out.append(rr)
    return out


def _mmr_select(query: str, records: List[Dict[str, Any]], top_n: int = 6, lambda_: float = 0.65) -> List[Dict[str, Any]]:
    if not query or not records:
        return []
    qv = embed(query)
    # Precompute similarities
    sims: List[Tuple[float, Dict[str, Any]]] = []
    for r in records:
        v = r.get("vec") or []
        if not isinstance(v, list) or not v:
            continue
        try:
            s = cosine(qv, v, len(v))
        except Exception:
            continue
        sims.append((s, r))
    if not sims:
        return []
    sims.sort(key=lambda x: x[0], reverse=True)

    selected: List[Dict[str, Any]] = []
    cand = [r for _, r in sims]

    def sim(a: Dict[str, Any], b: Dict[str, Any]) -> float:
        va = a.get("vec") or []
        vb = b.get("vec") or []
        if not isinstance(va, list) or not isinstance(vb, list) or not va or not vb:
            return 0.0
        try:
            return cosine(va, vb, len(va))
        except Exception:
            return 0.0

    while cand and len(selected) < max(1, int(top_n)):
        best = None
        best_score = -1e9
        for r in cand:
            # relevance
            try:
                rel = cosine(qv, r.get("vec") or [], len(r.get("vec") or []))
            except Exception:
                rel = 0.0
            # diversity
            div = 0.0
            for s in selected:
                div = max(div, sim(r, s))
            score = lambda_ * rel - (1 - lambda_) * div
            if score > best_score:
                best_score = score
                best = r
        if best is None:
            break
        selected.append(best)
        cand = [r for r in cand if r is not best]
    return selected


def _tfidf_tokens(text: str) -> List[str]:
    if _tok_hybrid is not None:
        try:
            return _tok_hybrid(text)
        except Exception:
            pass
    return re.findall(r"[A-Za-zА-Яа-я0-9_]+", (text or "").lower())


def _tfidf_rank(query: str, docs: List[Dict[str, Any]], top_k: int = 6) -> List[Dict[str, Any]]:
    if not query or not docs:
        return []
    tokens = _tfidf_tokens(query)
    if not tokens:
        return docs[: max(1, int(top_k))]

    # build df
    df: Dict[str, int] = {}
    tf_docs: List[Dict[str, float]] = []
    for d in docs:
        t = _tfidf_tokens(d.get("_txt", ""))
        counts: Dict[str, int] = {}
        for tok in t:
            counts[tok] = counts.get(tok, 0) + 1
        max_tf = max(counts.values()) if counts else 1
        tf = {k: v / max_tf for k, v in counts.items()}
        tf_docs.append(tf)
        for k in set(counts.keys()):
            df[k] = df.get(k, 0) + 1
    n = max(1, len(docs))
    idf = {k: math.log((1 + n) / (1 + v)) + 1.0 for k, v in df.items()}

    def vec_for(toks: List[str]) -> Dict[str, float]:
        counts: Dict[str, int] = {}
        for tok in toks:
            counts[tok] = counts.get(tok, 0) + 1
        max_tf = max(counts.values()) if counts else 1
        v = {}
        for k, c in counts.items():
            v[k] = (c / max_tf) * idf.get(k, 0.0)
        return v

    qv = vec_for(tokens)

    def cosine_dict(a: Dict[str, float], b: Dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        dot = 0.0
        for k, w in a.items():
            if k in b:
                dot += w * b[k]
        na = math.sqrt(sum(w * w for w in a.values()))
        nb = math.sqrt(sum(w * w for w in b.values()))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for i, d in enumerate(docs):
        sc = cosine_dict(qv, tf_docs[i])
        if sc > 0.0:
            scored.append((sc, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[: max(1, int(top_k))]]


def _load_cards() -> List[Dict[str, Any]]:
    persist_dir = (os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))).strip()
    path = os.path.join(persist_dir, "ester_cards.json")
    if not os.path.exists(path):
        return []
    try:
        data = json.load(open(path, "r", encoding="utf-8")) or {}
    except Exception:
        return []
    users = data.get("users") or {}
    out: List[Dict[str, Any]] = []
    for _uid, cards in users.items():
        if not isinstance(cards, list):
            continue
        for c in cards:
            if not isinstance(c, dict):
                continue
            text = c.get("text") or c.get("body") or c.get("header") or ""
            text = str(text or "").strip()
            if not text:
                continue
            cc = dict(c)
            cc["_txt"] = text
            out.append(cc)
    return out


def retrieve(
    query: str,
    *,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    topk_summary: int = 4,
    topk_chunks: int = 8,
    mmr_top_n: int = 6,
    topk_flashback: int = 6,
    topk_cards: int = 4,
) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"context": "", "provenance": [], "stats": {"used": False}}

    context_parts: List[str] = []
    provenance: List[Dict[str, Any]] = []
    stats = {
        "used": True,
        "doc_query": bool(is_doc_query(q)),
        "resolved_doc": False,
        "summary_hits": 0,
        "chunk_hits": 0,
        "semantic_doc_hits": 0,
        "flashback_hits": 0,
        "flashback_filtered": 0,
        "cards_hits": 0,
    }

    if _resolve_doc_for_query is not None and _build_doc_context is not None:
        try:
            resolved = _resolve_doc_for_query(q, chat_id=chat_id, user_id=user_id)
        except Exception:
            resolved = None
        if isinstance(resolved, dict):
            try:
                payload = _build_doc_context(resolved, q)
            except Exception:
                payload = {}
            ctx = str(payload.get("context") or "").strip() if isinstance(payload, dict) else ""
            prov = list(payload.get("provenance") or []) if isinstance(payload, dict) else []
            if ctx:
                stats["resolved_doc"] = True
                stats["summary_hits"] = 1 if "[SUMMARY]" in ctx else 0
                stats["chunk_hits"] = max(0, len(prov) - 1)
                reason = str(payload.get("reason") or "").strip() if isinstance(payload, dict) else ""
                if reason.startswith("semantic_"):
                    stats["semantic_doc_hits"] = 1
                return _finalize_response([ctx], prov, stats)

    # 1) doc_summary
    doc_summaries = _vector_rank(q, _collect_records_by_type(["doc_summary"]), topk_summary)
    if doc_summaries:
        stats["summary_hits"] = len(doc_summaries)
        lines = []
        for r in doc_summaries:
            text = (r.get("text") or "").strip()
            meta = r.get("meta") if isinstance(r.get("meta"), dict) else {}
            doc_id = str(meta.get("doc_id") or "")
            path = _norm_path(str(meta.get("source") or meta.get("source_path") or ""))
            lines.append(f"- {text}")
            provenance.append({
                "doc_id": doc_id,
                "path": path,
                "page": None,
                "offset": None,
            })
        context_parts.append("[DOC_SUMMARY]\n" + "\n".join(lines))

    # 2) doc_chunks with MMR
    chunk_candidates = _vector_rank(q, _collect_records_by_type(["doc_chunk"]), max(20, int(topk_chunks) * 4))
    chunk_selected = _mmr_select(q, chunk_candidates, top_n=mmr_top_n)
    if chunk_selected:
        stats["chunk_hits"] = len(chunk_selected)
        lines = []
        for r in chunk_selected[: max(1, int(topk_chunks))]:
            text = (r.get("text") or "").strip()
            meta = r.get("meta") if isinstance(r.get("meta"), dict) else {}
            doc_id = str(meta.get("doc_id") or "")
            path = _norm_path(str(meta.get("source") or meta.get("source_path") or ""))
            cite = str(meta.get("citation") or "")
            page = _parse_citation_page(cite)
            offset = meta.get("chunk_index")
            lines.append(f"- {text}")
            provenance.append({
                "doc_id": doc_id,
                "path": path,
                "page": page,
                "offset": offset,
            })
        context_parts.append("[DOC_CHUNKS]\n" + "\n".join(lines))

    # 3) structured flashback (facts/events)
    flash_types = ["fact", "event"]
    flash = _vector_rank(q, _collect_records_by_type(flash_types), topk_flashback)
    flash, filtered_out = _scope_flashback_records(flash, chat_id=chat_id, user_id=user_id)
    stats["flashback_filtered"] = int(filtered_out)
    if flash:
        stats["flashback_hits"] = len(flash)
        lines = []
        for r in flash[: max(1, int(topk_flashback))]:
            text = (r.get("text") or "").strip()
            tp = str(r.get("type") or "fact")
            lines.append(f"- ({tp}) {text}")
        context_parts.append("[FLASHBACK]\n" + "\n".join(lines))

    # 4) cards TF-IDF fallback
    cards = _load_cards()
    cards_hits = _tfidf_rank(q, cards, top_k=topk_cards) if cards else []
    if cards_hits:
        stats["cards_hits"] = len(cards_hits)
        lines = []
        for c in cards_hits[: max(1, int(topk_cards))]:
            lines.append(f"- {str(c.get('_txt') or '').strip()}")
        context_parts.append("[CARDS_TFIDF]\n" + "\n".join(lines))

    return _finalize_response(context_parts, provenance, stats)


_METRICS: Dict[str, int] = {
    "calls_total": 0,
    "router_used": 0,
    "doc_queries": 0,
    "summary_hits": 0,
    "chunk_hits": 0,
    "semantic_doc_hits": 0,
    "flashback_hits": 0,
    "cards_hits": 0,
    "provenance_items": 0,
    "last_ts": 0,
}
_LAST_LOG_TS = 0


def _finalize_response(
    context_parts: List[str],
    provenance: List[Dict[str, Any]],
    stats: Dict[str, Any],
) -> Dict[str, Any]:
    _METRICS["calls_total"] += 1
    _METRICS["router_used"] += 1
    if stats.get("doc_query"):
        _METRICS["doc_queries"] += 1
    _METRICS["summary_hits"] += int(stats.get("summary_hits") or 0)
    _METRICS["chunk_hits"] += int(stats.get("chunk_hits") or 0)
    _METRICS["semantic_doc_hits"] += int(stats.get("semantic_doc_hits") or 0)
    _METRICS["flashback_hits"] += int(stats.get("flashback_hits") or 0)
    _METRICS["cards_hits"] += int(stats.get("cards_hits") or 0)
    _METRICS["provenance_items"] += int(len(provenance))
    _METRICS["last_ts"] = int(time.time())
    _maybe_log_self_evo(stats, len(provenance))

    return {
        "context": "\n\n".join([p for p in context_parts if p]).strip(),
        "provenance": provenance,
        "stats": stats,
    }

def _maybe_log_self_evo(stats: Dict[str, Any], prov_len: int) -> None:
    global _LAST_LOG_TS
    try:
        interval = int(os.getenv("ESTER_RETRIEVAL_LOG_INTERVAL_SEC", "60") or 60)
    except Exception:
        interval = 60
    now = int(time.time())
    if interval > 0 and (now - int(_LAST_LOG_TS)) < interval:
        return
    _LAST_LOG_TS = now
    try:
        text = (
            f"RETRIEVAL_ROUTER used=1 "
            f"doc_query={int(bool(stats.get('doc_query')))} "
            f"prov={int(prov_len)} "
            f"summary={int(stats.get('summary_hits') or 0)} "
            f"chunks={int(stats.get('chunk_hits') or 0)} "
            f"semantic_docs={int(stats.get('semantic_doc_hits') or 0)} "
            f"flash={int(stats.get('flashback_hits') or 0)} "
            f"cards={int(stats.get('cards_hits') or 0)}"
        )
        memory_add("fact", text, meta={"type": "retrieval_router", "scope": "internal", "ts": now})
    except Exception:
        pass

def snapshot_metrics_to_memory() -> None:
    """
    Lightweight snapshot for self-evo: writes current router counters into memory.
    """
    try:
        m = get_metrics()
        text = (
            f"RETRIEVAL_ROUTER_SNAPSHOT calls={m.get('calls_total')} "
            f"doc_queries={m.get('doc_queries')} summary_hits={m.get('summary_hits')} "
            f"chunk_hits={m.get('chunk_hits')} semantic_doc_hits={m.get('semantic_doc_hits')} "
            f"flash_hits={m.get('flashback_hits')} "
            f"cards_hits={m.get('cards_hits')} prov_items={m.get('provenance_items')}"
        )
        memory_add("fact", text, meta={"type": "retrieval_router_snapshot", "scope": "internal", "ts": int(time.time())})
        _append_snapshot_files(m)
    except Exception:
        pass


def _snapshot_dir() -> str:
    base = (os.getenv("ESTER_STATE_DIR") or os.getenv("ESTER_HOME") or os.getenv("ESTER_ROOT") or os.getcwd()).strip()
    return os.path.join(base, "data", "metrics")


def _append_snapshot_files(m: Dict[str, Any]) -> None:
    try:
        os.makedirs(_snapshot_dir(), exist_ok=True)
    except Exception:
        pass

    ts = int(time.time())
    row = {
        "ts": ts,
        "calls_total": m.get("calls_total", 0),
        "router_used": m.get("router_used", 0),
        "doc_queries": m.get("doc_queries", 0),
        "summary_hits": m.get("summary_hits", 0),
        "chunk_hits": m.get("chunk_hits", 0),
        "semantic_doc_hits": m.get("semantic_doc_hits", 0),
        "flashback_hits": m.get("flashback_hits", 0),
        "cards_hits": m.get("cards_hits", 0),
        "provenance_items": m.get("provenance_items", 0),
    }

    # JSONL
    try:
        path = os.path.join(_snapshot_dir(), "retrieval_router_snapshots.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # CSV (append; write header if file absent)
    try:
        csv_path = os.path.join(_snapshot_dir(), "retrieval_router_snapshots.csv")
        exists = os.path.exists(csv_path)
        with open(csv_path, "a", encoding="utf-8", newline="") as f:
            if not exists:
                f.write(",".join(row.keys()) + "\n")
            f.write(",".join(str(row[k]) for k in row.keys()) + "\n")
    except Exception:
        pass

def get_metrics() -> Dict[str, Any]:
    return dict(_METRICS)

def get_metrics_text() -> str:
    m = _METRICS
    return (
        f"retrieval_router_calls_total {m['calls_total']}\n"
        f"retrieval_router_used_total {m['router_used']}\n"
        f"retrieval_router_doc_queries_total {m['doc_queries']}\n"
        f"retrieval_router_summary_hits_total {m['summary_hits']}\n"
        f"retrieval_router_chunk_hits_total {m['chunk_hits']}\n"
        f"retrieval_router_semantic_doc_hits_total {m['semantic_doc_hits']}\n"
        f"retrieval_router_flashback_hits_total {m['flashback_hits']}\n"
        f"retrieval_router_cards_hits_total {m['cards_hits']}\n"
        f"retrieval_router_provenance_items_total {m['provenance_items']}\n"
        f"retrieval_router_last_ts {m['last_ts']}\n"
    )


__all__ = ["retrieve", "is_doc_query", "get_metrics", "get_metrics_text", "snapshot_metrics_to_memory"]
