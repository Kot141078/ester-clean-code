# rebuild_structured_index.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List

from structured_memory import StructuredMemory
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _find_memory_file(dir_path: str) -> str | None:
    """Ischem ester_memory*.json v ukazannoy direktorii."""
    if not os.path.isdir(dir_path):
        return None
    names = [
        n
        for n in os.listdir(dir_path)
        if n.lower().endswith(".json") and "ester" in n and "memory" in n
    ]
    # prioritet — strogo ester_memory.json
    if "ester_memory.json" in names:
        return os.path.join(dir_path, "ester_memory.json")
    return os.path.join(dir_path, names[0]) if names else None


def _rebuild(path: str) -> None:
    if not os.path.isfile(path):
        print(f"[!] Memory file not found: {path}")
        sys.exit(2)

    sm = StructuredMemory(path)
    fixed = sm.heal()

    # Polnaya peresborka indeksa ryadom s pamyatyu (kollektsiya obychno 'structured_mem')
    sm.vstore.docs = {}
    count = 0
    for user, entries in (sm.memory or {}).items():
        if not isinstance(entries, list):
            continue
        for e in entries:
            if not isinstance(e, dict):
                continue
            if ("query" in e or "answer" in e) and "id" in e:
                text = f"{(e.get('query') or '').strip()}\n{(e.get('answer') or '').strip()}"
                meta = {
                    "user": user,
                    "timestamp": e.get("timestamp"),
                    "tags": e.get("tags", []),
                }
                sm.vstore.bulk_add([(e["id"], text, meta)])
                count += 1

    print(f"[OK] heal_fixed={fixed}, reindexed={count}")
    print(f"[OK] store_path={sm.vstore.store_path}")


def main():
    ap = argparse.ArgumentParser(description="Rebuild structured_mem index from memory JSON")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--path", help="Polnyy put k ester_memory.json")
    g.add_argument(
        "--dir",
        help="Direktoriya, gde lezhit pamyat (skript sam naydet ester_memory*.json)",
    )
    g.add_argument(
        "--auto",
        action="store_true",
        help="Vzyat direktoriyu iz config.PERSIST_DIR i iskat tam fayl pamyati",
    )

    args = ap.parse_args()

    mem_path: str | None = None

    if args.path:
        mem_path = os.path.abspath(args.path)
    elif args.dir:
        d = os.path.abspath(args.dir)
        mem_path = _find_memory_file(d)
    elif args.auto:
        try:
            from config import PERSIST_DIR

            d = os.path.abspath(PERSIST_DIR)
            mem_path = _find_memory_file(d) or os.path.join(d, "ester_memory.json")
        except Exception as e:
            print(f"[!] Ne udalos prochitat config.PERSIST_DIR: {e}")
            sys.exit(2)

    if not mem_path:
        print(
            "[!] Ne nashli fayl pamyati. Ukazhi --path ili --dir, libo ispolzuy --auto pri korrektnom PERSIST_DIR."
        )
        sys.exit(2)

    _rebuild(mem_path)


if __name__ == "__main__":
    main()
