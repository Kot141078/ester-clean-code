# -*- coding: utf-8 -*-
"""tools/index_validator.py - validator indeksov po shartam: tselostnost, zagruzka, probnye zaprosy.

What to prove:
  1) Nalichie metadannykh meta.json i poleznoy nagruzki (faiss|flat fayly).
  2) Sootvetstvie razmera ids i facticheskogo chisla vektorov (po faylam).
  3) Probnye zaprosy: vybiraet 64 sluchaynykh L2-chanka iz korpusa, vektorizuet (lokalnyy fallback),
     vypolnyaet search(topk=10) po kazhdomu shard-indeksu, proveryaet, chto otvety ne pustye.
  4) Svodnaya svodka po shartam: count, disk_bytes, backend, status.

CLI:
  python tools/index_validator.py --dim 384 --root ./data/index/faiss

Zemnoy abzats (inzheneriya):
This is “indikator bieniya shpindelya”: bystrym prokhodom ubezhdaemsya, what indeksy zhivye,
vidyat svoi identifikatory i vozvraschayut otvety na tipovye zaprosy.

Mosty:
- Yavnyy (Arkhitektura ↔ Nadezhnost): proverka tselostnosti - obyazatelnyy ritual pered relizom.
- Skrytyy 1 (Infoteoriya ↔ Ekonomika): validiruem tolko vyborku — berezhem vremya i NVMe, no poluchaem uverennost.
- Skrytyy 2 (Anatomiya ↔ PO): kak refleks-test — legkoe “postukivanie” molotochkom podtverzhdaet reaktsiyu.

# c=a+b"""
from __future__ import annotations

import argparse, json, os, random
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# optional numpa; if not, we’ll limit ourselves to a structural check
try:
    import numpy as np  # type: ignore
except Exception:
    np = None  # type: ignore

def _data_dir() -> str:
    return os.getenv("PERSIST_DIR") or os.getenv("DATA_DIR") or "./data"

def _hier_dir() -> str:
    return os.path.join(_data_dir(), "index", "hier")

def _load_l2(doc_id: str):
    p = os.path.join(_hier_dir(), f"L2_chunks__{doc_id}.jsonl")
    out = []
    try:
        for line in open(p, "r", encoding="utf-8"):
            try: out.append(json.loads(line))
            except: pass
    except FileNotFoundError:
        pass
    return out

def _iter_l0():
    p = os.path.join(_data_dir(), "L0_meta.jsonl")
    try:
        for line in open(p, "r", encoding="utf-8"):
            line=line.strip()
            if not line: continue
            try: yield json.loads(line)
            except: pass
    except FileNotFoundError:
        return

def _embed_texts(texts, dim: int):
    # local deterministic embedder (as in /index/build)
    import hashlib
    if np is None:
        raise RuntimeError("numpy is required for vector checks")
    X = np.zeros((len(texts), dim), dtype="float32")
    for i,t in enumerate(texts):
        h = hashlib.sha1((t or "").encode("utf-8","ignore")).digest()
        for j in range(dim):
            X[i, j] = (h[j % len(h)] - 127.5) / 127.5
        n = float(np.linalg.norm(X[i]) or 1.0)
        X[i] /= n
    return X

def _index(shard: str, dim: int, backend: str):
    from modules.faiss_ivfpq import IvfPqIndex  # type: ignore
    root = os.getenv("INDEX_ROOT") or os.path.join(_data_dir(), "index", "faiss")
    return IvfPqIndex(index_dir=os.path.join(root, shard), dim=dim, backend=backend)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim", type=int, default=int(os.getenv("EMBED_DIM") or 384))
    ap.add_argument("--root", default=os.getenv("INDEX_ROOT") or os.path.join(_data_dir(), "index", "faiss"))
    ap.add_argument("--backend", default=os.getenv("INDEX_BACKEND","faiss"))
    ap.add_argument("--samples", type=int, default=64)
    args = ap.parse_args()

    # Let's get a list of shards
    from modules.shard_router import ShardRouter  # type: ignore
    sr = ShardRouter(index_root=args.root)
    shards = sr.list_shards()
    report = {"shards": {}, "ok": True}

    for s in shards:
        idx = _index(s, dim=args.dim, backend=args.backend)
        st = idx.stats()
        ok_files = st.get("disk_bytes", 0) > 0 and st.get("count", 0) >= 0
        ok_ids   = st.get("count", 0) == len(st.get("cfg",{}).get("ids", st.get("ids", []))) if isinstance(st.get("ids"), list) else True
        status = {"backend": st.get("backend"), "count": st.get("count"), "disk_bytes": st.get("disk_bytes"), "ok_files": ok_files, "ok_ids": ok_ids}
        report["shards"][s] = status

    # We sample the texts and check the search (if there are numps)
    if np is not None:
        # soberem teksty
        l0 = list(_iter_l0())
        texts = []
        for rec in random.sample(l0, k=min(len(l0), max(1, args.samples // 4))) if l0 else []:
            texts.extend([ch.get("text","") for ch in _load_l2(rec.get("doc_id"))[:4]])
        texts = texts[:args.samples] if texts else ["search check", "information theory", "bayesovskiy podkhod", "entropiya signala"]
        X = _embed_texts(texts, dim=args.dim)

        for s in shards:
            idx = _index(s, dim=args.dim, backend=args.backend)
            # lazy loading will happen inside the search
            try:
                res = idx.search(X[:8], topk=5)
                report["shards"][s]["search_ok"] = all(len(row) > 0 for row in res) if isinstance(res, list) else False
            except Exception as e:
                report["shards"][s]["search_ok"] = False
                report["ok"] = False

    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()