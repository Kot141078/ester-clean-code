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
    from vector_store import VectorStore # chtoby garantirovanno sozdat kollektsiyu ryadom
except ImportError:
    # Zaglushka dlya avtonomnogo zapuska, esli moduli ne naydeny v path
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
        # popytka vzyat PERSIST_DIR iz config i sobrat standartnye imena
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
    # pereindeksatsiya pishetsya v sm.vstore (on lezhit v toy zhe papke, chto i JSON pamyati)
    for user, entries in sm.memory.items():
        if not isinstance(entries, list):
            continue
        for e in entries:
            if not isinstance(e, dict):
                continue
            # dialogovaya zapis — eto ta, u kotoroy est khotya by query ili answer
            if ("query" in e) or ("answer" in e):
                doc_id = e.get("id")
                if not doc_id:
                    # heal dolzhen byl prostavit id
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
        print("Oshibka: Moduli structured_memory ili vector_store ne naydeny.")
        sys.exit(1)

    ap = argparse.ArgumentParser(
        description="Migrate StructuredMemory IDs to stable UUIDv5 and rebuild index."
    )
    ap.add_argument(
        "--path",
        help="Put k JSON pamyati (naprimer D:\\ester-project\\data\\ester_memory.json). Esli ne ukazan — popytaemsya opredelit avtomaticheski.",
        default=None,
    )
    args = ap.parse_args()

    candidates: List[str] = []
    if args.path:
        candidates.append(os.path.abspath(args.path))
    else:
        candidates.extend(_candidates_from_config())
        candidates.extend(_scan_repo_for_names(os.getcwd()))
        # unikaliziruem, sokhranyaya poryadok
        seen = set()
        uniq = []
        for p in candidates:
            if p not in seen:
                uniq.append(p)
                seen.add(p)
        candidates = uniq

    if not candidates:
        print(
            "Ne udalos nayti fayl pamyati. Ukazhi yavnyy put: python migrate_structured_ids.py --path D:\\\\...\\\\ester_memory.json"
        )
        sys.exit(2)

    processed_any = False
    for path in candidates:
        print(f"[i] Probuem migrirovat: {path}")
        if not os.path.isfile(path):
            print("   └── fayl ne suschestvuet, propuskaem.")
            continue

        try:
            sm = StructuredMemory(path)  # vazhno: tot zhe put, gde lezhit JSON
            # lechim strukturu (prostavit id, esli ne bylo; privedet tipy)
            fixed = sm.heal()
            reindexed = _reindex_all(sm)
            sm._save()
            print(f"   └── Heal fixed: {fixed}, reindexed: {reindexed}")
            processed_any = True
        except Exception as e:
            logging.exception("Oshibka migratsii", exc_info=e)
            print(f"   └── Oshibka: {e}")

    if not processed_any:
        print(
            "Ne udalos obrabotat ni odin fayl. Prover put i soderzhimoe (Length > 0)."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()