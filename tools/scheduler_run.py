# -*- coding: utf-8 -*-
"""
CLI — lokalnyy planirovschik: scan/apply "tikom" bez fonovykh demonov.

Most (yavnyy):
- (CLI ↔ UI) Te zhe operatsii dostupny i v terminale, i v adminke.

Mosty (skrytye):
- (Nadezhnost ↔ Ekonomika) Dry-run po umolchaniyu sokraschaet shans nevernoy zapisi.
- (Formaty ↔ Operatsii) Rabotaet s txt/md/pdf bez vneshnikh bibliotek — prosche deploy.

Zemnoy abzats:
Utilita skaniruet `ESTER/inbox/{txt,md,pdf}`, pokazyvaet plan i (v B) pishet zadaniya v
`ESTER/state/queue/*.json`. V A — tolko prevyu.

# c=a+b
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from modules.scheduler.watcher import WatchConfig, plan_tick, apply_tick
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()

def main():
    ap = argparse.ArgumentParser(description="Local scheduler tick (A/B).")
    ap.add_argument("--scan", action="store_true", help="Tolko pokazat plan (dry)")
    ap.add_argument("--apply", action="store_true", help="Sozdat zadachi (tolko v B)")
    ap.add_argument("--limit", type=int, default=None, help="Limit faylov za tik")
    ap.add_argument("--no-chunk", action="store_true", help="Otklyuchit razbienie teksta")
    ap.add_argument("--max-bytes", type=int, default=None, help="Predel razmera fayla")
    args = ap.parse_args()

    cfg = WatchConfig()
    if args.limit is not None:
        cfg.limit_files = args.limit
    if args.max_bytes is not None:
        cfg.max_bytes = args.max_bytes
    if args.no_chunk:
        cfg.enable_chunking = False

    if args.apply:
        res = apply_tick(cfg)
    else:
        res = plan_tick(cfg)

    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res.get("ok"):
        if args.apply:
            print(f"[OK] AB={AB_MODE} apply: {res.get('added')} items")
        else:
            print(f"[OK] AB={AB_MODE} scan: {res.get('count')} items planned")
    else:
        print("[ERR] operation failed")

if __name__ == "__main__":
    raise SystemExit(main())
