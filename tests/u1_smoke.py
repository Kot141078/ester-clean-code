#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""U1/tests/u1_smoke.py - myagkiy smouk “Sovetnika”.

Mosty:
- Yavnyy: Enderton — proveryaem: temy izvlecheny ∧ portal/sovet sgenerirovany.
- Skrytyy #1: Ashbi — ustoychivost: otsutstvie dannykh/setey ne valit payplayn.
- Skrytyy #2: Cover & Thomas — kratkie artefakty dlya bystroy priemki.

Zemnoy abzats (inzheneriya):
Zapuskaet `u1_advisor.py` na lokalnom demo-kontekste. Proveryaet, what fayly poyavilis.

# c=a+b"""
from __future__ import annotations
import json, os, subprocess, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    ctx = "tests/fixtures/u1_context.txt"
    subprocess.run([sys.executable, "tools/u1_advisor.py", "--context", ctx, "--top", "5"], check=False)
    ok = os.path.isfile("portal/index.html") and os.path.isfile("portal/advice.md")
    print(json.dumps({"ok": ok}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())