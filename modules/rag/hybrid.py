# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules/rag/hybrid.py - gibridnyy retriver (fallback JSONL) s "maloy vydachey".

Changes v6:
- Po umolchaniyu otdaem tolko SNIPPET (obrezka) vmesto polnogo teksta.
- Polnyy tekst vklyuchaem TOLKO pri include_text=true (or cherez ENV HYBRID_INCLUDE_TEXT=1).
- Upravlenie dlinoy snippeta: max_chars (parameter zaprosa) or ENV HYBRID_SNIPPET_CHARS (by default 600).
- Sovmestimost: polya "items" i "hits" ostayutsya; add "snippet" i "len_text".

MOSTY:
- Yavnyy: /rag/hybrid/search ↔ etot modul - parameter include_text/max_chars.
- Skrytye:
  1) ENV ↔ Answer: HYBRID_SNIPPET_CHARS, HYBRID_INCLUDE_TEXT.
  2) Dannye ↔ Transport: umenshaem JSON (snippet), predotvraschaya megabaytnye otvety.
ZEMNOY ABZATs:
Bolshie dokumenty (mnogomegabaytnye) zabivayut set/klient. Snippet - inzhenerno razumnyy
kompromiss: bystryy predprosmotr + yavnoe vklyuchenie polnogo teksta po zaprosu.
# c=a+b"""
import os, re, math, json
from typing import List, Dict, Any, Tuple, Optional, Iterable
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_DOCS_CACHE: List[Dict[str, Any]] = []
_TOKS: List[Dict[str, float]] = []   # tf-vektory
_IDF: Dict[str, float] = {}
_BUILT: bool = False
_PATH: str = ""

_TOKEN_RX = re.compile(r"[A-Za-zA-Yaa-ya0-9_]+", re.UNICODE)
_KEY_PREFS = ("value","text","content","body","summary","abstract","caption")

def _tok(s: str) -> List[str]:
    if not isinstance(s, str):
        s = str(s)
    return [t.lower() for t in _TOKEN_RX.findall(s)]

def _join_strings(xs: Iterable[str]) -> str:
    return " ".join([x for x in xs if isinstance(x, str) and x])

def _strings_in(obj: Any) -> List[str]:
    out: List[str] = []
    if obj is None:
        return out
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k in _KEY_PREFS:
            v = obj.get(k)
            if isinstance(v, str) and v:
                out.append(v)
                break
        for v in obj.values():
            out.extend(_strings_in(v))
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            out.extend(_strings_in(v))
    return out

def _extract_text(entry: Dict[str, Any]) -> str:
    raw = entry.get("text", "")
    if isinstance(raw, str):
        return raw
    strings = _strings_in(raw)
    return _join_strings(strings).strip()

def _build_once() -> None:
    global _BUILT, _DOCS_CACHE, _TOKS, _IDF, _PATH
    if _BUILT:
        return
    _PATH = os.getenv("HYBRID_FALLBACK_DOCS", "").strip() or "data/mem/docs.jsonl"
    docs: List[Dict[str, Any]] = []
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                txt = _extract_text(obj)
                if not txt:
                    continue
                obj["_txt"] = txt
                docs.append(obj)
    except FileNotFoundError:
        docs = []
    _DOCS_CACHE = docs

    tf_list: List[Dict[str, float]] = []
    df: Dict[str, int] = {}
    for obj in _DOCS_CACHE:
        toks = _tok(obj.get("_txt", ""))
        if not toks:
            tf_list.append({})
            continue
        counts: Dict[str, int] = {}
        for t in toks:
            counts[t] = counts.get(t, 0) + 1
        max_tf = max(counts.values()) if counts else 1
        tf = {t: c / max_tf for t, c in counts.items()}
        tf_list.append(tf)
        for t in set(counts.keys()):
            df[t] = df.get(t, 0) + 1

    n = max(len(_DOCS_CACHE), 1)
    idf = {t: math.log((1 + n) / (1 + dfc)) + 1.0 for t, dfc in df.items()}
    _TOKS = tf_list
    _IDF = idf
    _BUILT = True

def _cosine(qv: Dict[str, float], dv: Dict[str, float]) -> float:
    if not qv or not dv:
        return 0.0
    dot = 0.0
    for t, w in qv.items():
        if t in dv:
            dot += w * dv[t]
    nq = math.sqrt(sum(w*w for w in qv.values()))
    nd = math.sqrt(sum(w*w for w in dv.values()))
    if nq == 0.0 or nd == 0.0:
        return 0.0
    return dot / (nq * nd)

def _tfidf(tokens: List[str]) -> Dict[str, float]:
    if not tokens:
        return {}
    counts: Dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    max_tf = max(counts.values()) if counts else 1
    v = {}
    for t, c in counts.items():
        tf = c / max_tf
        idf = _IDF.get(t, 0.0)
        v[t] = tf * idf
    return v

def _make_item(obj: Dict[str, Any], sc: float, *, include_text: bool, max_chars: int) -> Dict[str, Any]:
    full = obj.get("_txt", "")
    snippet = full if max_chars is None or max_chars <= 0 else full[:max_chars]
    item = {
        "id": str(obj.get("id", "")),
        "score": float(sc),
        "snippet": snippet,
        "len_text": len(full),
        "meta": obj.get("meta", {}),
    }
    if include_text:
        item["text"] = full
    return item

def _run(query: str, top_k: int = 6, **kwargs) -> Dict[str, Any]:
    _build_once()
    tokens = _tok(query or "")
    qv = _tfidf(tokens)

    # max_chars
    max_chars = kwargs.get("max_chars", None)
    if max_chars is None:
        try:
            max_chars = int(os.getenv("HYBRID_SNIPPET_CHARS", "600"))
        except Exception:
            max_chars = 600
    else:
        try:
            max_chars = int(max_chars)
        except Exception:
            max_chars = 600

    # include_text
    include_text = kwargs.get("include_text", None)
    if include_text is None:
        include_text = (os.getenv("HYBRID_INCLUDE_TEXT", "0").strip().lower() in ("1","true","yes","on"))
    else:
        include_text = bool(include_text)

    scored: List[Tuple[int, float]] = []
    for i, dv in enumerate(_TOKS):
        score = _cosine(qv, dv)
        if score > 0.0:
            scored.append((i, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    k = int(top_k or 6)
    out_items: List[Dict[str, Any]] = []
    for i, sc in scored[:k]:
        obj = _DOCS_CACHE[i]
        out_items.append(_make_item(obj, sc, include_text=include_text, max_chars=max_chars))

    return {
        "ok": True,
        "items": out_items,
        "hits": out_items,
        "backend": "fallback-jsonl",
        "docs_path": _PATH,
        "count_indexed": len(_DOCS_CACHE),
        "max_chars": max_chars,
        "include_text": bool(include_text),
    }

def hybrid_search(query: str, top_k: int = 6, **kwargs) -> Dict[str, Any]:
    return _run(query=query, top_k=top_k, **kwargs)

def search(query: Optional[str] = None, top_k: int = 6, **kwargs) -> Dict[str, Any]:
    if not query:
        for key in ("query", "q", "text", "prompt", "input"):
            if key in kwargs and isinstance(kwargs[key], str):
                query = kwargs[key]
                break
    if not isinstance(top_k, int):
        try:
            top_k = int(top_k)
        except Exception:
            top_k = 6
    if top_k == 6:
        for k in ("top_k", "k", "limit", "n_results", "n"):
            if k in kwargs:
                try:
                    top_k = int(kwargs[k])
                except Exception:
                    pass
                break
    return _run(query or "", top_k=top_k, **kwargs)
# c=a+b