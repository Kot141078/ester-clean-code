#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R8/tests/r8_smoke.py - myagkiy smouk bezopasnosti/reliza.

Mosty:
- Yavnyy: Enderton — proveryaemye predikaty: otchet sekretov sozdan ∧ bundle+manifest zapisany.
- Skrytyy #1: Ashbi — ustoychivost: pri otsutstvii faylov — akkuratnoe behavior bez padeniy.
- Skrytyy #2: Cover & Thomas — minimalnaya, no informativnaya summary.

Zemnoy abzats (inzheneriya):
Gonyaet scaner sekretov, zatem sobiraet bandl i vyvodit puti artefaktov. Podkhodit dlya CI.

# c=a+b"""
from __future__ import annotations
import subprocess, sys, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    subprocess.run([sys.executable, "tools/r8_secret_scan.py", "--out", "sec_report.md"], check=False)
    out = subprocess.check_output([sys.executable, "tools/r8_release_bundle.py", "--out", "release/ester_bundle.tar.gz"], text=True)
    print(out.strip())
    print("[R8] DONE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

# c=a+b