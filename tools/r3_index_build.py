#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R3/tools/r3_index_build.py — CLI dlya postroeniya TF-IDF indeksa po kartochkam Ester.

Mosty:
- Yavnyy: Cover & Thomas — IDF snizhaet izbytochnost, povyshaya vklad redkikh terminov.
- Skrytyy #1: Enderton — CLI kak predikaty parametrov (net parametrov → defoltnyy bild).
- Skrytyy #2: Ashbi — A/B-slot cherez R3_MODE, pri oshibkakh B → avtokatbek v A.

Zemnoy abzats:
Zapuskaetsya bez argumentov, stroit/perezapisyvaet indeks (JSON) v `PERSIST_DIR/reco`.
Podkhodit dlya cron/planirovschika. Tolko stdlib.

# c=a+b
"""
from __future__ import annotations
import json
from services.reco.tfidf_index import build_index  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    n = build_index()
    print(json.dumps({"ok": 1, "docs_indexed": n}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())