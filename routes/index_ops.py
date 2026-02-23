# -*- coding: utf-8 -*-
"""
routes/index_ops.py - JSON-operatsii indeksov: build/rebuild/stats/snapshot.

Marshruty (Blueprint "index_ops_bp"):
  POST /index/build     { shard?:str, level?: "L1"|"L2", strategy?: "ivfpq"|"flat", params?: {...} }
  GET  /index/stats
  POST /index/snapshot  { shard?:str }

Povedenie:
  • build: sobiraet ili peresobiraet indeks po shardam, chitaya L2-chanki iz
    ./data/index/hier/L2_chunks__<doc_id>.jsonl i L0-metu iz ./data/L0_meta.jsonl.
    Vektorizatsiya: modules.embedder.embed_texts(texts)->np.ndarray[float32] (esli net - fallback khesh-embedder).
  • stats: vozvraschaet razmery/schetchiki po shartam i konfiguratsiyu indeksov.
  • snapshot: delaet tar.{zst|gz} v SNAPSHOT_DIR (po umolchaniyu ./data/snapshots).

Bezopasnost:
  • Dlya prostoty seychas otkryto; v prode obernut JWT/rol admin|ops.

Zemnoy abzats (inzheneriya)
Eti ruchki - «pult operatora stanka»: sobrat indeks, posmotret razmery, snyat snapshot.
Vse lokalno, prozrachno i bez vneshnikh zavisimostey.

Mosty
- Yavnyy (Arkhitektura ↔ Operatsii): build/stats/snapshot - minimalnyy DevOps-kontur bez vneshnego orkestratora.
- Skrytyy 1 (Infoteoriya ↔ Ekonomika): stroim tolko to, chto nuzhno (po shardam) - ekonomim vremya i NVMe.
- Skrytyy 2 (Anatomiya ↔ PO): kak inventarizatsiya organov - znaem massu/obem indeksa i mozhem bystro «zamorozit» snimok.

# c=a+b
"""
from __future__ import annotations

import io
import json
import os
import tarfile
import time
from typing import Any, Dict, Iterable, List, Tuple

from flask import Blueprint, Response, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Optsionalnaya zavisimost
try:
    import numpy as np  # type: ignore
except Exception:
    np = None  # type: ignore

# Lokalnye moduli
def _data_dir() -> str:
    return os.getenv("PERSIST_DIR") or os.getenv("DATA_DIR") or "./data"

def _index_root() -> str:
    return os.path.join(_data_dir(), "index", "faiss")

def _hier_dir() -> str:
    return os.path.join(_data_dir(), "index", "hier")

def _snapshot_dir() -> str:
    return os.getenv("SNAPSHOT_DIR") or os.path.join(_data_dir(), "snapshots")

def _backend(strategy: str | None) -> str:
    if strategy and strategy.lower() == "flat":
        return "flat"
    return (os.getenv("INDEX_BACKEND") or "faiss").strip().lower()

# --- prostoy fallback-embedder (determinirovannyy) ---
def _hash_embed(texts: List[str], dim: int) -> "np.ndarray":  # type: ignore
    import hashlib, math
    if np is None:
        raise RuntimeError("numpy is required")
    out = np.zeros((len(texts), dim), dtype="float32")
    for i, t in enumerate(texts):
        h = hashlib.sha1((t or "").encode("utf-8", errors="ignore")).digest()
        # razmazhem bayty po izmereniyam (povtorno)
        for j in range(dim):
            b = h[j % len(h)]
            out[i, j] = (float(b) - 127.5) / 127.5
        # L2-normirovka
        n = float(np.linalg.norm(out[i]) or 1.0)
        out[i] /= n
    return out

def _embed_texts(texts: List[str], dim: int) -> "np.ndarray":  # type: ignore
    # Popytka vyzvat polzovatelskiy embedder
    try:
        from modules import embedder  # type: ignore
        vecs = embedder.embed_texts(texts, dim=dim)  # type: ignore
        return vecs
    except Exception:
        return _hash_embed(texts, dim)

# --- i/o utility dlya L0/L2 ---
def _iter_l0() -> Iterable[Dict]:
    p = os.path.join(_data_dir(), "L0_meta.jsonl")
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except Exception:
                        continue
    except FileNotFoundError:
        return

def _load_l2(doc_id: str) -> List[Dict]:
    p = os.path.join(_hier_dir(), f"L2_chunks__{doc_id}.jsonl")
    out: List[Dict] = []
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return out

# --- shardirovanie i indeksy ---
def _router():
    from modules.shard_router import ShardRouter  # type: ignore
    return ShardRouter(index_root=_index_root(), strategy=os.getenv("SHARD_STRATEGY"))

def _index_for_shard(shard: str, dim: int, backend: str):
    from modules.faiss_ivfpq import IvfPqIndex  # type: ignore
    idx_dir = os.path.join(_index_root(), shard)
    return IvfPqIndex(index_dir=idx_dir, dim=dim, backend=backend)

# Blueprint
index_ops_bp = Blueprint("index_ops_bp", __name__)

@index_ops_bp.route("/build", methods=["POST"])
def index_build() -> Response:
    """
    Sobiraet indeksy po shardam iz L2-chankov.
    Parametry JSON:
      - shard?: string (esli ukazan - tolko etot shard)
      - level?: "L1"|"L2" (seychas ispolzuetsya L2)
      - strategy?: "ivfpq"|"flat" (inache iz ENV INDEX_BACKEND)
      - params?: { dim?: int, nlist?: int, m?: int, bits?: int, nprobe?: int }
    """
    if np is None:
        return jsonify({"ok": False, "error": "numpy_required"}), 500

    payload = request.get_json(force=True, silent=True) or {}
    level = (payload.get("level") or os.getenv("INDEX_LEVEL") or "L2").strip().upper()
    strat = (payload.get("strategy") or "ivfpq").strip().lower()
    backend = _backend("flat" if strat == "flat" else None)
    params = payload.get("params") or {}
    dim = int(params.get("dim") or os.getenv("EMBED_DIM") or 384)
    nlist = int(params.get("nlist") or os.getenv("IVF_NLIST") or 65536)
    m = int(params.get("m") or os.getenv("PQ_M") or 96)
    bits = int(params.get("bits") or os.getenv("PQ_BITS") or 8)

    router = _router()
    shards_req = [payload["shard"]] if payload.get("shard") else router.list_shards()
    router.ensure_shard_dirs(shards_req)

    # Soberem teksty i metu → raspredelim po shardam
    # doc_id -> meta
    meta_by_doc: Dict[str, Dict] = {}
    for rec in _iter_l0():
        meta_by_doc[rec.get("doc_id")] = rec

    # shard -> (texts, ids)
    bucket_texts: Dict[str, List[str]] = {s: [] for s in shards_req}
    bucket_ids: Dict[str, List[str]] = {s: [] for s in shards_req}

    total_chunks = 0
    for doc_id, meta in meta_by_doc.items():
        l2 = _load_l2(doc_id)
        if not l2:
            continue
        # meta dlya shardirovaniya
        mdoc = {
            "title": meta.get("title"),
            "authors": meta.get("authors") or [],
            "chars": sum(int(x.get("chars") or 0) for x in l2),
        }
        shard = router.shard_for_doc(mdoc)
        if shard not in bucket_texts:
            continue  # ne etot shard
        for ch in l2:
            bucket_texts[shard].append(ch.get("text") or "")
            bucket_ids[shard].append(f"{doc_id}:{int(ch.get('i') or 0)}")
            total_chunks += 1

    # Obuchenie/sborka po shardam
    t0 = time.time()
    built = []
    for shard in shards_req:
        texts = bucket_texts.get(shard) or []
        ids = bucket_ids.get(shard) or []
        if not texts:
            continue
        vecs = _embed_texts(texts, dim=dim)
        idx = _index_for_shard(shard, dim=dim, backend=backend)
        info = idx.build(vecs, ids, nlist=nlist, m=m, bits=bits)
        built.append({"shard": shard, "info": info})

    return jsonify({
        "ok": True,
        "level": level,
        "backend": backend,
        "dim": dim,
        "nlist": nlist,
        "m": m,
        "bits": bits,
        "total_chunks": total_chunks,
        "built": built,
        "ms": round(1000 * (time.time() - t0), 2),
    })

@index_ops_bp.route("/stats", methods=["GET"])
def index_stats() -> Response:
    router = _router()
    shards = router.list_shards()
    out = {"ok": True, "shards": [], "manifest": router.manifest()}
    backend = (os.getenv("INDEX_BACKEND") or "faiss").strip().lower()
    dim = int(os.getenv("EMBED_DIM") or 384)
    for s in shards:
        idx = _index_for_shard(s, dim=dim, backend=backend)
        st = idx.stats()
        st["shard"] = s
        out["shards"].append(st)
    return jsonify(out)

@index_ops_bp.route("/snapshot", methods=["POST"])
def index_snapshot() -> Response:
    payload = request.get_json(force=True, silent=True) or {}
    shard = payload.get("shard")  # esli None - vse
    index_root = _index_root()
    snapdir = _snapshot_dir()
    os.makedirs(snapdir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"index__{shard or 'all'}__{stamp}.tar"
    tar_path = os.path.join(snapdir, name)

    # Vybor papok
    targets: List[str] = []
    if shard:
        p = os.path.join(index_root, shard)
        if os.path.isdir(p):
            targets.append(p)
    else:
        for s in os.listdir(index_root):
            p = os.path.join(index_root, s)
            if os.path.isdir(p):
                targets.append(p)
    if not targets:
        return jsonify({"ok": False, "error": "no_shards"}), 400

    # Sozdaem tar
    with tarfile.open(tar_path, mode="w") as tar:
        for p in targets:
            tar.add(p, arcname=os.path.relpath(p, start=index_root))
    # Poprobuem szhat zstd → gz
    zst_path = tar_path + ".zst"
    try:
        import zstandard as zstd  # type: ignore
        cctx = zstd.ZstdCompressor(level=10)
        with open(tar_path, "rb") as src, open(zst_path, "wb") as dst:
            dst.write(cctx.compress(src.read()))
        os.remove(tar_path)
        final_path = zst_path
        algo = "zstd"
    except Exception:
        import gzip
        gz_path = tar_path + ".gz"
        with open(tar_path, "rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
            dst.write(src.read())
        os.remove(tar_path)
        final_path = gz_path
        algo = "gzip"

    return jsonify({"ok": True, "snapshot": final_path, "algo": algo})


def register(app):
    app.register_blueprint(index_ops_bp)
    return app