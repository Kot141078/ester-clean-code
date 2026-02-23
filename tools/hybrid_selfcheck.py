#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/hybrid_selfcheck.py — proverka dostupnosti komponentov gibridnogo poiska.

Proveryaem:
  • ENV: HYBRID_SEARCH_AB, HYBRID_ALPHA, HYBRID_COARSE_LIMIT
  • coarse: modules.hier_index.search_coarse ili StructuredMemory.search_bm25
  • dense: modules.memory.vector_store.vector_search ili VectorStore.search / vstore_simple.VStore.search

Vykhod: JSON-otchet.

Mosty:
- Yavnyy: (Nablyudaemost ↔ Poisk) bystro vidno, pochemu gibrid ne rabotaet.
- Skrytyy #1: (Inzheneriya ↔ Podderzhka) bez vneshnikh zavisimostey.
- Skrytyy #2: (Kibernetika ↔ Resursy) kontrol parametrov ansamblya (alpha/limit).

Zemnoy abzats:
Eto kak proverit, chto u tebya est i polka, i skaner shtrikhkodov — inache ansambl ne zavedetsya.

# c=a+b
"""
from __future__ import annotations

import json
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _have_hier() -> bool:
    try:
        from modules import hier_index  # noqa: F401
        return True
    except Exception:
        return False

def _have_sm_bm25() -> bool:
    try:
        from structured_memory import StructuredMemory  # type: ignore
        sm = StructuredMemory()
        return hasattr(sm, "search_bm25")
    except Exception:
        return False

def _have_vector() -> bool:
    try:
        from modules.memory.vector_store import vector_search  # type: ignore
        _ = vector_search
        return True
    except Exception:
        pass
    try:
        from structured_memory import VectorStore  # type: ignore
        vs = VectorStore()
        return hasattr(vs, "search")
    except Exception:
        pass
    try:
        import vstore_simple  # type: ignore
        vs = getattr(vstore_simple, "VStore", None)
        return vs is not None
    except Exception:
        return False

def main(argv=None) -> int:
    rep = {
        "env": {
            "HYBRID_SEARCH_AB": os.getenv("HYBRID_SEARCH_AB", "A"),
            "HYBRID_ALPHA": os.getenv("HYBRID_ALPHA", "0.55"),
            "HYBRID_COARSE_LIMIT": os.getenv("HYBRID_COARSE_LIMIT", "50"),
        },
        "coarse": {
            "hier_index": _have_hier(),
            "structured_memory_bm25": _have_sm_bm25(),
        },
        "dense": {
            "vector_backend_present": _have_vector()
        },
        "ok": True
    }
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
