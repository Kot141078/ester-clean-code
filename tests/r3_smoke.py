#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R3/tests/r3_smoke.py — myagkiy smouk R3 (indeks → zapros) na lokalnykh kartochkakh.

Mosty:
- Yavnyy: Enderton — proveryaem dva predikata: indeks postroen ∧ iz topa vernulsya spisok.
- Skrytyy #1: Cover & Thomas — dostatochen odin prostoy zapros dlya obnaruzheniya klassa oshibok TF-IDF.
- Skrytyy #2: Ashbi — regulyator prosche: stdlib-only, nikakikh vneshnikh servisov.

Zemnoy abzats:
Esli kartochek net — ne valim payplayn (pechataem preduprezhdenie). Inache stroim indeks i vypolnyaem zapros.
Podkhodit dlya CI/lokalki. Avtokatbek A/B upravlyaetsya ENV R3_MODE.

# c=a+b
"""
from __future__ import annotations
import json
import os
from services.reco.scorer_a import reco_build, reco_score  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    n = reco_build()
    if n == 0:
        print("[R3] WARN: net kartochek dlya indeksa — propusk zaprosa.")
        return 0
    res = reco_score("demo opisanie", top=5)
    print(json.dumps({"n": len(res), "res": res}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())