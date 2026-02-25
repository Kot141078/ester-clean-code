# -*- coding: utf-8 -*-
"""scripts/repair_vectorstores.py — proverka i legkiy remont vektornykh storadzhey.
Action:
  - Proveryaet nalichie kollektsii v VectorStore
  - Pri neobkhodimosti sozdaet pustuyu kollektsiyu
  - Pechataet bazovuyu statistiku (chislo vektorov/dokov)

Zapusk:
  python scripts/repair_vectorstores.py
ENV:
  PERSIST_DIR, COLLECTION_NAME, USE_EMBEDDINGS, EMBEDDINGS_*"""
from __future__ import annotations

import json
import os
from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _persist_dir() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(base, exist_ok=True)
    return base


def repair(collection_name: str, persist_dir: str) -> str:
    """
    Repair legacy JSON vectorstore file by removing empty-text docs.
    Returns repaired file path.
    """
    path = os.path.join(persist_dir, f"{collection_name}.json")
    if not os.path.exists(path):
        from vector_store import VectorStore  # type: ignore

        vs = VectorStore(collection_name=collection_name, persist_dir=persist_dir, use_embeddings=False)
        path = str(vs.path)

    payload = json.loads(open(path, "r", encoding="utf-8").read() or "{}")
    docs = payload.get("docs")
    if not isinstance(docs, dict):
        docs = {}
    fixed = {}
    for doc_id, row in docs.items():
        text = str((row or {}).get("text") or "").strip()
        if not text:
            continue
        fixed[str(doc_id)] = dict(row or {})
    payload["docs"] = fixed
    payload.setdefault("alias_map", {})
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


def main() -> int:
    try:
        from vector_store import VectorStore  # type: ignore
    except Exception as e:
        print("VectorStore module not found:", e)
        return 2

    vs = VectorStore(
        collection_name=os.getenv("COLLECTION_NAME", "ester_store"),
        persist_dir=_persist_dir(),
        use_embeddings=bool(int(os.getenv("USE_EMBEDDINGS", "0"))),
        embeddings_api_base=os.getenv("EMBEDDINGS_API_BASE", ""),
        embeddings_model=os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        embeddings_api_key=os.getenv("EMBEDDINGS_API_KEY", ""),
        use_local=bool(int(os.getenv("EMBEDDINGS_USE_LOCAL", "1"))),
    )
    try:
        st = vs.stats()  # type: ignore[attr-defined]
    except Exception:
        # let's create an empty collection using the trick: upsert the zero element (which will not be saved)
        try:
            vs.ensure_collection()  # type: ignore[attr-defined]
            st = vs.stats()  # type: ignore[attr-defined]
        except Exception as e:
            print("Failed to ensure collection:", e)
            return 3

    print(json.dumps({"ok": True, "vectorstore": st}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    main()
