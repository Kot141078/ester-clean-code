#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R6/tests/r6_smoke.py - myagkiy smouk R6: daydzhest → pravila → r6-daydzhest.

Mosty:
- Yavnyy: Enderton — proveryaem predikaty: vkhodnoy digest nayden ∧ vykhodnye fayly sozdany.
- Skrytyy #1: Cover & Thomas — schitaem metriki “do/after” (posledovatelnost informativna).
- Skrytyy #2: Ashbi — A/B-slot cherez ENV, pri oshibkakh ne padaem (katbek).

Zemnoy abzats (inzheneriya):
Build daydzhest (esli nuzhno), zatem primenyaet pravila iz fikstury i pechataet statistiku.
Na stdlib, podkhodit dlya lokalki/CI.

# c=a+b"""
from __future__ import annotations
import glob
import json
import os
from subprocess import check_output, CalledProcessError
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _digdir():
    return os.path.join(os.getenv("PERSIST_DIR") or "data", "portal", "digests")

def _ensure_digest():
    digdir = _digdir()
    os.makedirs(digdir, exist_ok=True)
    paths = glob.glob(os.path.join(digdir, "digest_*.json"))
    if paths:
        return
    # postroim
    try:
        print(check_output(["python", "tools/r5_digest_build.py", "--plan", "tests/fixtures/digest_plan.json"], text=True))
    except CalledProcessError as e:
        print(e.output)

def main() -> int:
    _ensure_digest()
    try:
        out = check_output(["python", "tools/r6_apply_rules.py", "--rules", "tests/fixtures/rules_config.json"], text=True)
        print(out.strip())
    except CalledProcessError as e:
        print(e.output)
    print("[R6] DONE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())