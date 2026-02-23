#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R4/tools/r4_rerank_cli.py — CLI: poluchit rerank+summary dlya zaprosa (B-slot s avtokatbekom).

Mosty:
- Yavnyy: Enderton — formalnye predikaty nad parametrami i rezultatami (JSON).
- Skrytyy #1: Ashbi — ustoychivost: pri oshibke LLM vozvraschaem A-rezultat.
- Skrytyy #2: Cover & Thomas — kratkiy, no informativnyy vyvod (score_a/score_b/summary) snizhaet neopredelennost.

Zemnoy abzats:
Rabotaet s LM Studio (esli R4_MODE=B i servis dostupen) ili bez nego (A-rezhim).
Vyvod — chelovekochitaemyy JSON (UTF-8). Udobno dlya payplayna daydzhesta/portala.

# c=a+b
"""
from __future__ import annotations
import argparse
import json
from typing import List
from services.reco.bslot_rerank import bslot_rerank  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    ap = argparse.ArgumentParser(description="R4 rerank+summary (B-slot with fallback)")
    ap.add_argument("--query", required=True, help="Tekst zaprosa")
    ap.add_argument("--top", type=int, default=5, help="Skolko vernut")
    ap.add_argument("--tags", default="", help="Filtr po tegam: comma-separated")
    args = ap.parse_args()

    tags: List[str] = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    res = bslot_rerank(args.query, top=args.top, tags=tags or None)
    print(json.dumps({"ok": 1, "results": res}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())