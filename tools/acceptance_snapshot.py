# -*- coding: utf-8 -*-
"""CLI - finalnyy snapshot priemki.

Most (yavnyy):
- (CLI ↔ UX) Bystryy zapusk itogovogo otcheta iz terminala.

Mosty (skrytye):
- (Infoteoriya ↔ Ekspluatatsiya) Kanonichnyy JSON-vyvod legok dlya avtomaticheskoy proverki.
- (Logika ↔ Nadezhnost) A/B-predokhranitel — bez zapisi po umolchaniyu.

Zemnoy abzats:
Komanda sobiraet marshruty/ENV/artefakty i, esli zaprosheno, pishet finalnyy otchet v `ESTER/reports/final_compliance.json`.

# c=a+b"""
from __future__ import annotations

import argparse
import json
import os

from modules.acceptance.snapshot import gather_snapshot, gather_and_maybe_write
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()

def main():
    ap = argparse.ArgumentParser(description="Final acceptance snapshot (A/B).")
    ap.add_argument("--write", action="store_true", help="Write report (B-mode will write to disk)")
    args = ap.parse_args()

    if args.write:
        res = gather_and_maybe_write()
    else:
        res = gather_snapshot()

    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res.get("ok", False):
        print(f"[OK] AB={AB_MODE} written={res.get('written', False)}")
    else:
        print("[FAIL]")
        raise SystemExit(1)

if __name__ == "__main__":
    main()
# c=a+b