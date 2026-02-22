# -*- coding: utf-8 -*-
"""
modules/search/hybrid_retriever.py — gibridnyy retriver (BM25/Hier + Dense) s obedineniem i normirovkoy.

API:
  • hybrid_search(q:str, k:int=8, scope:dict|None=None) -> dict
  • counters() -> dict  — metriki

Algoritm:
  1) Coarse/BM25: probuem ierarkhicheskiy indeks (esli est) ili faylovyy indeks video-segmentov (fallback).
  2) Dense: probuem vektornyy sloy (esli dostupen) cherez standartnye klienty (best-effort).
  3) Sliyanie: normiruem [0..1], RRF (reciprocal rank fusion) + vesa, vyrezaem dublikaty po id/sha.
  4) Vozvraschaem edinyy spisok items: {"id","text","score","meta","tags"}.

Mosty:
- Yavnyy: (Memory ↔ Poisk) obedinyaem silnye storony sparse i dense retriva.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) RRF daet ustoychivost k promakham odnogo iz kanalov.
- Skrytyy #2: (Logika ↔ Video) umeet chitat `.index.jsonl` segmenty (pakety VideoQA+Index).
- Novoe: (Mesh/P2P ↔ Raspredelennost) sinkhronizatsiya kesha khitov mezhdu agentami Ester.
- Novoe: (Cron ↔ Avtonomiya) refresh indeksa/cleanup kesha dlya svezhesti.
- Novoe: (Monitoring ↔ Prozrachnost) webhook na low-hits/low-score dlya audita.

Zemnoy abzats:
Eto «dvoynoy lokator»: snachala nakhodim rayon po slovam, zatem tochnee tselimsya po smyslu — i obedinyaem rezultaty, keshiruem, delimsya po P2P, obnovlyaem po cron — chtoby poisk Ester byl molnienosnym, bez promakhov v BZ.

# c=a+b
"""
from __future__ import annotations
import glob, json, os, re, math, time, hashlib
from typing import Any, Dict, List, Tuple
import urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_CNT = {"calls_total": 0, "sparse_hits": 0, "dense_hits": 0}
CACHE_DB = os.getenv("SEARCH_CACHE_DB", "data/search/cache.json")
CACHE_MAX_AGE_DAYS = int(os.getenv("CACHE_MAX_AGE_DAYS", "7") or "7")
PEERS_STR = os.getenv("PEERS", "")  # "http://node1:port/sync,http://node2:port/sync"
PEERS = [p.strip() for p in PEERS_STR.split(",") if p.strip()]
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
MONITOR_HIT_THRESHOLD = int(os.getenv("MONITOR_HIT_THRESHOLD", "3") or "3")
MONITOR_SCORE_THRESHOLD = float(os.getenv("MONITOR_SCORE_THRESHOLD", "0.5") or "0.5")

state: Dict[str, Any] = {"updated": 0, "cache": {}, "last_refresh": int(time.time())}

def _ensure_cache():
    os.makedirs(os.path.dirname(CACHE_DB), exist_ok=True)
    if not os.path.isfile(CACHE_DB):
        json.dump({"cache": {}}, open(CACHE_DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load_cache():
    global state
    _ensure_cache()
    if os.path.isfile(CACHE_DB):
        try:
            loaded = json.load(open(CACHE_DB, "r", encoding="utf-8"))
            state["cache"].update(loaded.get("cache", {}))
            state["updated"] = loaded.get("updated", state["updated"])
            state["last_refresh"] = loaded.get("last_refresh", state["last_refresh"])
        except Exception:
            pass
    # Sinkh ot peers pri starte
    if PEERS:
        for peer in PEERS:
            try:
                req = urllib.request.Request(f"{peer}", method="GET")
                with urllib.request.urlopen(req, timeout=5) as r:
                    peer_state = json.loads(r.read().decode("utf-8"))
                    for key, data in peer_state.get("cache", {}).items():
                        if key not in state["cache"] or data["ts"] > state["cache"][key]["ts"]:
                            state["cache"][key] = data
            except Exception:
                pass

def _save_cache():
    state["updated"] = int(time.time())
    json.dump({"cache": state["cache"]}, open(CACHE_DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    _sync_cache_to_peers()

def _sync_cache_to_peers():
    if not PEERS:
        return
    body = json.dumps({"cache": state["cache"]}).encode("utf-8")
    for peer in PEERS:
        try:
            req = urllib.request.Request(f"{peer}", data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

def receive_sync(payload: Dict[str, Any]):
    _load_cache()
    for key, data in payload.get("cache", {}).items():
        if key not in state["cache"] or data["ts"] > state["cache"][key]["ts"]:
            state["cache"][key] = data
    _save_cache()

def _hash_key(q: str) -> str:
    return hashlib.sha256(q.encode("utf-8")).hexdigest()

def _tokenize(s: str) -> List[str]:
    return re.findall(r"[a-zA-Za-yaA-YaeE0-9\-]+", (s or "").lower())

def _bm25_like_score(q_tok: List[str], text: str) -> float:
    if not text:
        return 0.0
    toks = _tokenize(text)
    if not toks:
        return 0.0
    hits = sum(1 for t in toks if t in q_tok)
    if hits == 0:
        return 0.0
    return hits / math.sqrt(len(toks))

def _sparse_file_search(q: str, k: int) -> List[Dict[str, Any]]:
    q_tok = set(_tokenize(q))
    items = []
    for path in glob.glob("data/**/*.index.jsonl", recursive=True):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    it = json.loads(line)
                    text = it.get("text", "")
                    score = _bm25_like_score(q_tok, text)
                    if score > 0:
                        items.append({"id": it.get("id"), "text": text, "meta": it.get("meta", {}), "tags": it.get("tags", []), "score": score})
                except Exception:
                    pass
    items.sort(key=lambda x: x["score"], reverse=True)
    return items[:k * 2]  # overfetch for merge

def _dense_vs_search(q: str, k: int) -> List[Dict[str, Any]]:
    try:
        from modules.memory.vector_store import vector_search  # type: ignore
        rep = vector_search(q, k)
        if rep.get("ok"):
            return rep.get("items", [])
    except Exception:
        pass
    return []

def _coarse_candidates(q: str, limit: int) -> List[Dict[str, Any]]:
    try:
        from modules.hier_index import search_coarse  # type: ignore
        rep = search_coarse(q, limit)
        if rep.get("ok"):
            return rep.get("items", [])
    except Exception:
        pass
    try:
        from structured_memory import StructuredMemory  # type: ignore
        sm = StructuredMemory()
        return sm.search_bm25(q, limit)
    except Exception:
        pass
    return _sparse_file_search(q, limit)

def _rerank_dense(q: str, pool: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
    try:
        from modules.memory.vector_store import rerank_dense  # type: ignore
        rep = rerank_dense(q, pool, k)
        if rep.get("ok"):
            return rep.get("items", [])
    except Exception:
        pass
    try:
        from structured_memory import VectorStore  # type: ignore
        vs = VectorStore()
        return vs.search(q, pool=pool, k=k)
    except Exception:
        pass
    return pool[:k]  # fallback no rerank

def _minmax_norm(vals: List[float]) -> List[float]:
    if not vals:
        return []
    v_min = min(vals)
    v_max = max(vals)
    if v_min == v_max:
        return [1.0] * len(vals)
    return [(v - v_min) / (v_max - v_min) for v in vals]

def _rrf_merge(sparse: List[Dict[str, Any]], dense: List[Dict[str, Any]], k: int = 8, k0: int = 60) -> List[Dict[str, Any]]:
    bank: Dict[str, Dict[str, Any]] = {}
    ranks: Dict[str, float] = {}
    def add_list(lst: List[Dict[str, Any]], is_sparse: bool = True):
        for rank, it in enumerate(lst, 1):
            _id = it.get("id") or f"row:{hash(it.get('text', ''))}"
            if _id not in bank:
                bank[_id] = it
            score_key = "coarse" if is_sparse else "dense"
            bank[_id][score_key] = float(it.get("score", 0.0))
            ranks[_id] = ranks.get(_id, 0.0) + 1.0 / (k0 + rank)
    add_list(sparse, True)
    add_list(dense, False)
    merged = [{"id": _id, **bank[_id], "score": scr} for _id, scr in ranks.items()]
    merged.sort(key=lambda x: x["score"], reverse=True)
    out: List[Dict[str, Any]] = []
    seen = set()
    for it in merged:
        key = (it.get("id"), (it.get("text") or "")[:64])
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
        if len(out) >= k:
            break
    return out

def _env_ab() -> str:
    return os.getenv("HYBRID_SEARCH_AB", "A").upper().strip() or "A"

def _alpha() -> float:
    try:
        return float(os.getenv("HYBRID_ALPHA", "0.55"))
    except Exception:
        return 0.55

def _coarse_limit() -> int:
    try:
        return int(os.getenv("HYBRID_COARSE_LIMIT", "32"))
    except Exception:
        return 32

def cron_refresh():
    _load_cache()
    now = int(time.time())
    if now - state["last_refresh"] >= 86400:  # daily
        # Refresh sparse/dense indexes if methods available
        try:
            from modules.hier_index import refresh_index  # type: ignore
            refresh_index()
        except Exception:
            pass
        try:
            from structured_memory import StructuredMemory  # type: ignore
            sm = StructuredMemory()
            sm.refresh_bm25()
        except Exception:
            pass
        try:
            from modules.memory.vector_store import refresh_vs  # type: ignore
            refresh_vs()
        except Exception:
            pass
        # Cleanup cache
        to_remove = []
        for key, data in state["cache"].items():
            age_days = (now - data.get("ts", now)) / 86400
            if age_days > CACHE_MAX_AGE_DAYS:
                to_remove.append(key)
        for key in to_remove:
            del state["cache"][key]
        state["last_refresh"] = now
        _save_cache()
    return {"ok": True, "refresh_time": state["last_refresh"], "removed": len(to_remove)}

def config(alpha: float = None, coarse_limit: int = None) -> Dict[str, Any]:
    if alpha is not None:
        os.environ["HYBRID_ALPHA"] = str(alpha)
    if coarse_limit is not None:
        os.environ["HYBRID_COARSE_LIMIT"] = str(coarse_limit)
    return {"ok": True, "alpha": _alpha(), "coarse_limit": _coarse_limit()}

def counters() -> Dict[str, int]:
    return dict(_CNT)

def hybrid_search(q: str, k: int = 8, scope: Dict[str, Any] | None = None, alpha: float = None) -> Dict[str, Any]:
    _load_cache()
    cron_refresh()
    _CNT["calls_total"] += 1
    mode = _env_ab()
    a = _alpha() if alpha is None else float(alpha)
    used: Dict[str, Any] = {"coarse": None, "dense": None}
    key = _hash_key(q)
    if key in state["cache"]:
        entry = state["cache"][key]
        if (time.time() - entry["ts"]) / 86400 <= CACHE_MAX_AGE_DAYS:
            return {"ok": True, "mode": mode, "used": used, "items": entry["items"], "from_cache": True}
    if mode == "A":
        dense = _dense_vs_search(q, k)
        used["dense"] = "passthrough"
        items = dense[:k]
    else:
        coarse = _coarse_candidates(q, _coarse_limit())
        used["coarse"] = "available" if coarse else "none"
        _CNT["sparse_hits"] += len(coarse)
        if not coarse:
            dense = _dense_vs_search(q, k)
            used["dense"] = "fallback_only"
            items = dense[:k]
        else:
            pool = _rerank_dense(q, coarse, k)
            used["dense"] = "rerank"
            _CNT["dense_hits"] += len(pool)
            c_vals = [x.get("coarse", 0.0) for x in pool]
            d_vals = [x.get("dense", 0.0) for x in pool]
            c_norm = _minmax_norm(c_vals)
            d_norm = _minmax_norm(d_vals)
            fused = []
            for it, c, d in zip(pool, c_norm, d_norm):
                score = (1.0 - a) * c + a * d
                fused.append({"id": it.get("id"), "text": it.get("text"), "meta": it.get("meta", {}), "tags": it.get("tags", []), "score": score})
            items = _rrf_merge(coarse, fused, k)
    # Scope filter
    if scope and ("dump" in scope or "dump_id" in scope):
        dump_id = None
        if scope.get("dump"):
            dump_id = os.path.splitext(os.path.basename(scope["dump"]))[0]
        if scope.get("dump_id"):
            dump_id = scope.get("dump_id")
        if dump_id:
            flt = [it for it in items if f"dump:{dump_id}" in (it.get("tags") or []) or (it.get("meta") or {}).get("dump_id") == dump_id]
            if flt:
                items = flt[:k]
    # Cache
    state["cache"][key] = {"items": items, "ts": int(time.time())}
    _save_cache()
    # Webhook if low
    mean_score = sum(it["score"] for it in items) / len(items) if items else 0
    if WEBHOOK_URL and (len(items) < MONITOR_HIT_THRESHOLD or mean_score < MONITOR_SCORE_THRESHOLD):
        try:
            alert = {"q_len": len(q), "hits": len(items), "mean_score": mean_score, "ts": int(time.time())}
            body = json.dumps(alert).encode("utf-8")
            req = urllib.request.Request(WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
    try:
        from modules.mem.passport import append as _pp
        _pp("hybrid_search", {"hits": len(items), "mean_score": mean_score}, "search://hybrid")
    except Exception:
        pass
# return {"ok": True, "mode": mode, "used": used, "items": items}