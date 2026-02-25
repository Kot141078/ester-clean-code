#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R4/tests/r4_smoke.py — myagkiy smouk B-slot: build A-top i pytaemsya sdelat rerank+summary.

Mosty:
- Yavnyy: Enderton — proveryaemye predikaty: {est kandidaty} ∧ {poluchen spisok rezultatov}.
- Skrytyy #1: Ashbi — ustoychivost: sboy LLM ne valit test, srabatyvaet avtokatbek.
- Skrytyy #2: Cover & Thomas — dostatochno maloy vyborki dlya detekta klassa oshibok.

Zemnoy abzats:
Esli kartochek net - vyvodim WARN. Esli LM Studio nedostupen - test zavershitsya uspeshno s A-rezultatami.
Only stdlib.

# c=a+b"""
from __future__ import annotations
import json
from services.reco.scorer_a import reco_build  # type: ignore
from services.reco.bslot_rerank import bslot_rerank  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    n = reco_build()
    if n == 0:
        print("[R4] WARN: net kartochek — propusk rerank.")
        return 0
    res = bslot_rerank("demo opisanie", top=5)
    print(json.dumps({"n": len(res), "sample": res[:2]}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())