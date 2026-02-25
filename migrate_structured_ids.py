# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Importiruem nashi moduli
try:
    from structured_memory import StructuredMemory
    from vector_store import VectorStore # to be sure to create a collection nearby
except ImportError:
    # Stub for standalone launch if modules are not found in path
    StructuredMemory = None
    VectorStore = None


# ---------- utils ----------
def _exists_nonempty(p: str) -> bool:
    try:
        return os.path.isfile(p) and os.path.getsize(p) > 0
    except Exception:
        return False


def _candidates_from_config() -> List[str]:
    paths: List[str] = []
    try:
        # an attempt to take PERSIST_HOLES from the config and collect standard names
        from config import EsterConfig
        cfg = EsterConfig()
        base_mem = cfg.PATHS.get("memory", "data/memory")

        for name in ("ester_memory.json", "structured_memory.json"):
            p = os.path.join(base_mem, name)
            if os.path.isfile(p):
                paths.append(p)
    except Exception:
        pass
    return paths


def _scan_repo_for_names(
    root: str, names=("ester_memory.json", "structured_memory.json")
) -> List[str]:
    hits: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        for n in names:
            if n in filenames:
                hits.append(os.path.join(dirpath, n))
    return hits


def _reindex_all(sm: StructuredMemory) -> int:
    count = 0
    # reindexing is written in the sm.store (it is in the same folder as the JSON memory)
    for user, entries in sm.memory.items():
        if not isinstance(entries, list):
            continue
        for e in entries:
            if not isinstance(e, dict):
                continue
            # a dialogue entry is one that has at least cuers or answer
            if ("query" in e) or ("answer" in e):
                doc_id = e.get("id")
                if not doc_id:
                    # Heal should have put down the ID
                    continue
                text = f"{(e.get('query') or '').strip()}\n{(e.get('answer') or '').strip()}"
                meta = {
                    "user": user,
                    "timestamp": e.get("timestamp"),
                    "tags": e.get("tags", []),
                }
                if hasattr(sm, "vstore") and sm.vstore:
                     sm.vstore.bulk_add([(doc_id, text, meta)])
                     count += 1
    return count


# ---------- main ----------
def main():
    if StructuredMemory is None:
        print("Error: Structured_memory or vector_store modules not found.")
        sys.exit(1)

    ap = argparse.ArgumentParser(
        description="Migrate StructuredMemory IDs to stable UUIDv5 and rebuild index."
    )
    ap.add_argument(
        "--path",
        help="Path to memory JSION (for example D:eester-projectedataeestr_memory.Jsion). If not specified, we will try to determine it automatically.",
        default=None,
    )
    args = ap.parse_args()

    candidates: List[str] = []
    if args.path:
        candidates.append(os.path.abspath(args.path))
    else:
        candidates.extend(_candidates_from_config())
        candidates.extend(_scan_repo_for_names(os.getcwd()))
        # unique while maintaining order
        seen = set()
        uniq = []
        for p in candidates:
            if p not in seen:
                uniq.append(p)
                seen.add(p)
        candidates = uniq

    if not candidates:
        print(
            "The memory file could not be found. Provide an explicit path: pothon migrate_structured_ids.po --path D:uh...eeestier_memory.zsion"
        )
        sys.exit(2)

    processed_any = False
    for path in candidates:
        print(f"[i] Probuem migrirovat: {path}")
        if not os.path.isfile(path):
            print("   └── fayl ne suschestvuet, propuskaem.")
            continue

        try:
            sm = StructuredMemory(path)  # important: the same path where ZhSON lies
            # we treat the structure (put down the ID if it doesn’t exist; will list the types)
            fixed = sm.heal()
            reindexed = _reindex_all(sm)
            sm._save()
            print(f"   └── Heal fixed: {fixed}, reindexed: {reindexed}")
            processed_any = True
        except Exception as e:
            logging.exception("Migration Error", exc_info=e)
            print(f"   └── Oshibka: {e}")

    if not processed_any:
        print(
            "No files could be processed. Check the path and contents (Langth > 0)."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()