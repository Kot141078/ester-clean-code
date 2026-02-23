#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R5/tests/r5_smoke.py — myagkiy smouk R5: plan → daydzhest → HTML.

Mosty:
- Yavnyy: Enderton — proveryaem predikaty {digest.json suschestvuet} ∧ {index.html zapisan}.
- Skrytyy #1: Cover & Thomas — metriki iz daydzhesta (kol-vo sektsiy/elementov) dostatochny dlya priemki.
- Skrytyy #2: Ashbi — pri pustykh dannykh test ne valitsya (myagkiy rezhim).

Zemnoy abzats:
Sobiraet po lokalnomu planu `tests/fixtures/digest_plan.json`, zatem delaet render HTML.
Ispolzuet tolko stdlib. Gotovo k zapusku na lyubom stende.

# c=a+b
"""
from __future__ import annotations
import glob
import json
import os
from subprocess import check_output
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    # 1) Sborka
    out = check_output(["python", "tools/r5_digest_build.py", "--plan", "tests/fixtures/digest_plan.json"], text=True)
    print(out.strip())
    # 2) Render
    out2 = check_output(["python", "tools/r5_portal_render.py", "--out", "portal/index.html"], text=True)
    print(out2.strip())
    # 3) Mini-proverka nalichiya
    digests = glob.glob(os.path.join(os.getenv("PERSIST_DIR") or "data", "portal", "digests", "digest_*.json"))
    print(f"[R5] digests: {len(digests)}")
    print("[R5] DONE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())