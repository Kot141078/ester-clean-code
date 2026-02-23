#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R5/tools/r5_digest_build.py — CLI: sborka daydzhesta iz plana (JSON).

Mosty:
- Yavnyy: Enderton — predikaty plana (title/sections) → determinirovannyy rezultat (JSON/MD).
- Skrytyy #1: Cover & Thomas — kompaktnye summary i gruppirovka po tegam — maksimum signala, minimum shuma.
- Skrytyy #2: Ashbi — A/B-slot cherez R5_MODE (B s rasshireniyami; pri sboyakh — katbek).

Zemnoy abzats:
Chitaet plan (tests/fixtures/digest_plan.json ili svoy), stroit daydzhest cherez R4 (s fallback na A),
sokhranyaet JSON i MD v `PERSIST_DIR/portal/digests/`. Vozvraschaet puti v stdout.

# c=a+b
"""
from __future__ import annotations
import argparse
import json
from services.portal.digest_builder import build_digest, write_digest_files  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    ap = argparse.ArgumentParser(description="Sborka daydzhesta (R5)")
    ap.add_argument("--plan", required=True, help="Put k JSON-planu")
    args = ap.parse_args()

    plan = json.load(open(args.plan, "r", encoding="utf-8"))
    digest = build_digest(plan)
    out = write_digest_files(digest)
    print(json.dumps({"ok": 1, "out": out}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())