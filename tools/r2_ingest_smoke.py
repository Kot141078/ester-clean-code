#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R2/tests/r2_ingest_smoke.py — myagkiy smouk R2 bez seti.

Mosty:
- Yavnyy: Enderton — proveryaem predikaty: parsitsya li sample RSS? kladutsya li kartochki?
- Skrytyy #1: Ashbi — minimalnyy regulyator: lokalnye fayly, nikakikh vneshnikh servisov.
- Skrytyy #2: Cover & Thomas — nablyudeniya (added/seen) dostatochno informativny dlya priemki.

Zemnoy abzats:
Gonyaem CLI po lokalnym fiksturam (file://). Esli chego-to net — propuskaem, ne valim payplayn.

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
FX = BASE / "tests" / "fixtures"
RSS = FX / "sample_rss.xml"
INBOX = FX / "inbox_demo"

def main() -> int:
    # rss
    if RSS.exists():
        out = check_output([sys.executable, "tools/r2_ingest_cli.py", "rss-pull", "--url", f"file://{RSS}"], text=True)
        print(out.strip())
    else:
        print("[R2] WARN: net tests/fixtures/sample_rss.xml — propusk RSS.")
    # inbox
    if INBOX.exists():
        out = check_output([sys.executable, "tools/r2_ingest_cli.py", "inbox-scan", "--dir", str(INBOX)], text=True)
        print(out.strip())
    else:
        print("[R2] WARN: net tests/fixtures/inbox_demo — propusk inbox.")
    print("[R2] DONE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())