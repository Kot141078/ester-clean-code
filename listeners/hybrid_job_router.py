# -*- coding: utf-8 -*-
"""
listeners/hybrid_job_router.py — fonovye «tiki» gibridnoy ocheredi.

Povedenie:
  • Kazhdye HYBRID_POLL_SEC vyzyvaet dispatcher.tick_once().
  • V AB=A — sukhoy prokhod bez effektov.
  • Logi — kompaktnye JSON stroki v stdout.

Mosty:
- Yavnyy (Avtomatizatsiya ↔ Svyaznost): edinaya tochka pulsa gibridnoy ocheredi.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): periodicheskiy heartbeat i kratkie logi uproschayut diagnostiku.
- Skrytyy 2 (Praktika ↔ Sovmestimost): stdlib, offlayn, bez zhestkikh zavisimostey.

Zemnoy abzats:
Eto «mayatnik»: ravnomerno podtalkivaet ochered vpered, chtoby zadaniya dokhodili lyubym dostupnym putem.

# c=a+b
"""
from __future__ import annotations
import argparse, json, os, time
from modules.hybrid.dispatcher import tick_once  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester Hybrid Job Router")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--period", type=int, default=int(os.getenv("HYBRID_POLL_SEC","7")))
    args = ap.parse_args(argv)

    try:
        while True:
            res = tick_once()
            print(json.dumps({"ts": int(time.time()), "mod":"hybrid", "ab": AB, "processed": res.get("processed",0)}), flush=True)
            if not args.loop: break
            time.sleep(max(2, int(args.period)))
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b