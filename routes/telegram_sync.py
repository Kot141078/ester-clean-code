# -*- coding: utf-8 -*-
"""
scripts/telegram_sync.py - import Telegram-soobscheniy (JSON Updates) v pamyat «Ester».
Drop-in utilita: chitaet JSON (odin Update ili massiv Updates) iz fayla ili STDIN i pishet v StructuredMemory.

Ispolzovanie:
  python scripts/telegram_sync.py --file updates.json
  cat updates.json | python scripts/telegram_sync.py

ENV:
  PERSIST_DIR, COLLECTION_NAME, USE_EMBEDDINGS, EMBEDDINGS_* - dlya sborki MemoryManager (kak v drugikh modulyakh).

Mosty:
- Yavnyy: (Telegram ↔ Memory) konvertiruem obnovleniya chata v strukturirovannuyu pamyat.
- Skrytyy #1: (Infoteoriya ↔ Shum) filtratsiya nevernykh zapisey fiksiruet tolko uspeshnye insert'y.
- Skrytyy #2: (Kibernetika ↔ Konveyer) determinirovannyy stdout prigoden dlya payplaynov/orkestratorov.

Zemnoy abzats (anatomiya/inzheneriya):
Dumay ob etom kak o «sheykere dlya zametok»: berem portsiyu apdeytov, vstryakhivaem i akkuratno
vylivaem v konteyner pamyati. Emkost standartnaya, interfeysy - prostye i proveryaemye.

# c=a+b
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _build_mm():
    """Sobrat MemoryManager iz lokalnykh komponentov (bez zhestkikh zavisimostey)."""
    try:
        from cards_memory import CardsMemory  # type: ignore
        from memory_manager import MemoryManager  # type: ignore
        from structured_memory import StructuredMemory  # type: ignore
        from vector_store import VectorStore  # type: ignore
    except Exception as e:
        print(f"Cannot import memory components: {e}", file=sys.stderr)
        sys.exit(2)

    persist_dir = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(persist_dir, exist_ok=True)

    vstore = VectorStore(
        collection_name=os.getenv("COLLECTION_NAME", "ester_store"),
        persist_dir=persist_dir,
        use_embeddings=bool(int(os.getenv("USE_EMBEDDINGS", "0"))),
        embeddings_api_base=os.getenv("EMBEDDINGS_API_BASE", ""),
        embeddings_model=os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        embeddings_api_key=os.getenv("EMBEDDINGS_API_KEY", ""),
        use_local=bool(int(os.getenv("EMBEDDINGS_USE_LOCAL", "1"))),
    )
    structured = StructuredMemory(os.path.join(persist_dir, "structured_mem", "store.json"))  # type: ignore
    cards = CardsMemory(os.path.join(persist_dir, "ester_cards.json"))  # type: ignore
    return MemoryManager(vstore, structured, cards)  # type: ignore


def _read_updates(path: Optional[str]) -> List[Dict[str, Any]]:
    """Prochitat JSON s Update/Updates iz fayla (esli put zadan) ili iz STDIN."""
    try:
        if path:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        else:
            raw = sys.stdin.read()
        data = json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"cannot read updates: {e}")

    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError("expected JSON object or array")


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Import Telegram Updates into Ester memory")
    ap.add_argument("--file", help="Path to JSON file with Update or list of Updates", default=None)
    args = ap.parse_args(argv)

    try:
        from modules.telegram_adapter import TelegramAdapter  # type: ignore
    except Exception as e:
        print(f"Cannot import TelegramAdapter: {e}", file=sys.stderr)
        return 2

    mm = _build_mm()
    ta = TelegramAdapter(mm)
    try:
        updates = _read_updates(args.file)
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 2

    ok = 0
    for u in updates:
        try:
            rid = ta.process_update(u)  # type: ignore[attr-defined]
            if rid:
                ok += 1
        except Exception as e:
            # Logiruem oshibku, no prodolzhaem import sleduyuschikh zapisey
            print(f"update failed: {e}", file=sys.stderr)

    print(json.dumps({"ok": True, "imported": ok, "total": len(updates)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

# c=a+b


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
# zaglushka dlya telegram_sync: poka net bp/router/register_*_routes
def register(app):
    return True

# === /AUTOSHIM ===