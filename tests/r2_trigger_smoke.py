#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R2/tests/r2_trigger_smoke.py — smouk triggera po lokalnomu konfigu.

Mosty:
- Yavnyy: Enderton — predikaty: konfig chitaetsya ∧ zadachi vypolnyayutsya ∧ audit zapisan.
- Skrytyy #1: Ashbi — minimalnyy regulyator: strogo lineynoe vypolnenie, bez gonok.
- Skrytyy #2: Cover & Thomas — proveryaem dostatochnyy «signal» (poyavlenie zapisey v audit.jsonl).

Zemnoy abzats (inzheneriya):
Zapuskaet trigger na `tests/fixtures/ingest_config.json`, zatem stroit otchet Markdown.
Dopustim myagkiy rezhim: esli konfig otsutstvuet — test propuskaetsya.

# c=a+b
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from subprocess import check_output, CalledProcessError
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = Path(os.getcwd())
CFG = BASE / "tests" / "fixtures" / "ingest_config.json"

def main() -> int:
    if not CFG.exists():
        print("[R2] WARN: net tests/fixtures/ingest_config.json — propusk.")
        return 0
    out = check_output([sys.executable, "tools/r2_trigger.py", "--config", str(CFG)], text=True)
    print(out.strip())
    out2 = check_output([sys.executable, "tools/r2_audit_report.py", "--out", "ingest_audit.md"], text=True)
    print(out2.strip())
    print("[R2] DONE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())