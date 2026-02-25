#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3/tools/r3_score_cli.py - CLI dlya polucheniya top-N kartochek po tekstovomu zaprosu.

Mosty:
- Yavnyy: Enderton — zapros → predikaty nad indeksom (kosinusnoe skhodstvo) → determinirovannyy top-N.
- Skrytyy #1: Cover & Thomas - TF-IDF optimiziruet vklad redkikh priznakov.
- Skrytyy #2: Ashbi — A/B-slot cherez R3_MODE (bigrammy/svezhest).

Zemnoy abzats:
Udobno ispolzovat v payplayne daydzhesta ili dlya otladki kachestva.
Vyvod - JSON s polyami score/meta. Pri otsutstvii indeksa - build ego avtomaticheski.

# c=a+b"""
from __future__ import annotations
import argparse
import json
from typing import List
from services.reco.scorer_a import reco_score  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    ap = argparse.ArgumentParser(description="Score TF-IDF query over Ester cards")
    ap.add_argument("--query", required=True, help="Request text")
    ap.add_argument("--top", type=int, default=10, help="Razmer topa")
    ap.add_argument("--tags", default="", help="Filtr po tegam: comma-separated")
    args = ap.parse_args()

    tags: List[str] = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    res = reco_score(args.query, top=args.top, tags=tags or None)
    print(json.dumps({"ok": 1, "top": res}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())