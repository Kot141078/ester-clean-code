# -*- coding: utf-8 -*-
from __future__ import annotations

"""processing_worker.py - fonovaya “pochinka” khranilisch pamyati (heal_stores), s Celery or bez.

Pochemu padalo:
- `from celery import ...` → No module named 'celery' (u tebya Celery ne ustanovlen).
  Pri etom sam modul nuzhen vsego dlya periodicheskogo zapuska `heal_stores`. fileciteturn35file0

What was done:
- Esli Celery available: ispolzuem nastoyaschiy Celery (broker po ENV).
- Esli Celery net: ispolzuem `celery_shim` i daem CLI dlya sinkhronnogo zapuska:
    python processing_worker.py --once
    python processing_worker.py --loop --interval 24h

ENV:
- ESTER_CELERY_BROKER (po umolchaniyu redis://localhost:6379/0)
- ESTER_CELERY_BACKEND (optsionalno)
- WORKER_INTERVAL_SEC (esli --loop bez --interval)

Mosty:
- Yavnyy: planirovschik/vorker → heal_all() → ustoychivost pamyati.
- Skrytye:
  1) Infoteoriya ↔ ekspluatatsiya: “heal” kak periodicheskaya defragmentatsiya/sanatsiya kanala pamyati.
  2) Inzheneriya ↔ nadezhnost: Celery optional → kontur zhivet i bez Redis/ocheredey.

ZEMNOY ABZATs: v kontse fayla."""

import argparse
import os
import time
from typing import Any, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- Celery optional ---
_CELERY_AVAILABLE = False
try:
    from celery import Celery, shared_task  # type: ignore
    _CELERY_AVAILABLE = True
except Exception:
    from celery_shim import Celery, shared_task  # type: ignore

# --- project imports (best-effort) ---
def _import_first():
    # probuem “kornevye” moduli
    try:
        from vector_store import VectorStore  # type: ignore
        from structured_memory import StructuredMemory  # type: ignore
        from cards_memory import CardsMemory  # type: ignore
        from memory_manager import MemoryManager  # type: ignore
        return VectorStore, StructuredMemory, CardsMemory, MemoryManager
    except Exception:
        pass

    # probuem varianty vnutri modules.*
    try:
        from modules.memory.vector_store import VectorStore  # type: ignore
        from modules.memory.structured_memory import StructuredMemory  # type: ignore
        from modules.memory.cards_memory import CardsMemory  # type: ignore
        from modules.memory.memory_manager import MemoryManager  # type: ignore
        return VectorStore, StructuredMemory, CardsMemory, MemoryManager
    except Exception as e:
        raise ImportError(f"Cannot import Memory stack modules: {e}")


VectorStore, StructuredMemory, CardsMemory, MemoryManager = _import_first()


BROKER = (os.getenv("ESTER_CELERY_BROKER") or "redis://localhost:6379/0").strip()
BACKEND = (os.getenv("ESTER_CELERY_BACKEND") or "").strip()

# Celery app (realnyy ili shim)
app = Celery("ester", broker=BROKER, backend=BACKEND)


def _create_memory_manager():
    vstore = VectorStore()
    structured_mem = StructuredMemory()
    cards = CardsMemory()
    return MemoryManager(vstore, structured_mem, cards)


@shared_task
def heal_stores() -> Dict[str, Any]:
    """Background repair of storages (idea: once a day)."""
    mm = _create_memory_manager()
    res = mm.heal_all()
    # we are trying to make the result ZhSON-friendly
    try:
        if isinstance(res, dict):
            return {"ok": True, **res}
    except Exception:
        pass
    return {"ok": True, "result": str(res)}


def _parse_interval(s: str) -> int:
    s = (s or "").strip().lower()
    if not s:
        return int(os.getenv("WORKER_INTERVAL_SEC") or "86400")
    # format tipa 24h / 30m / 10s
    mul = 1
    if s.endswith("h"):
        mul = 3600
        s = s[:-1]
    elif s.endswith("m"):
        mul = 60
        s = s[:-1]
    elif s.endswith("s"):
        mul = 1
        s = s[:-1]
    try:
        return max(10, int(float(s) * mul))
    except Exception:
        return int(os.getenv("WORKER_INTERVAL_SEC") or "86400")


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Background worker: heal_stores (Celery optional)")
    ap.add_argument("--once", action="store_true", help="Run heal_stores once and exit")
    ap.add_argument("--loop", action="store_true", help="Run heal_stores in a loop")
    ap.add_argument("--interval", default="24h", help="Interval for --loop: 24n, 30m, 10s...")
    ap.add_argument("--print-env", action="store_true", help="Show mode (celers/shim) and broker")

    args = ap.parse_args(argv)

    if args.print_env:
        mode = "celery" if _CELERY_AVAILABLE else "shim"
        print(f"[INFO] mode={mode} broker={BROKER} backend={BACKEND or '-'}")
        return 0

    if args.once or not args.loop:
        out = heal_stores.delay() if hasattr(heal_stores, "delay") else heal_stores()  # type: ignore
        # Shim returns dist, celery returns AsinkResilt - print best-effort
        try:
            print(out)  # type: ignore
        except Exception:
            pass
        return 0

    interval = _parse_interval(args.interval)
    print(f"[INFO] loop interval={interval}s")
    while True:
        try:
            out = heal_stores.delay() if hasattr(heal_stores, "delay") else heal_stores()  # type: ignore
            try:
                print(out)  # type: ignore
            except Exception:
                pass
        except Exception as e:
            print(f"[WARN] heal_stores failed: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())


ZEMNOY = """ZEMNOY ABZATs (anatomiya/inzheneriya):
Etot vorker - kak nochnaya uborka na proizvodstve: dnem vse rabotayut, a nochyu kto-to dolzhen proytis,
podkrutit bolty, vykinut musor i ubeditsya, what linii ne zakhlamleny. Celery - eto brigada uborschikov s dispetcherom,
a shim - odin chelovek s klyuchom i fonarikom. Glavnoe - chtoby uborka voobsche proiskhodila."""