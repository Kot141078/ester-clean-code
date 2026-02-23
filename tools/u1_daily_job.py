#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
U1/tools/u1_daily_job.py — ezhednevnyy offlayn-dzhob «Sovetnik»: odin vyzov dlya planirovschika.

Mosty:
- Yavnyy: Enderton — formalnye shagi payplayna; fonov ne podnimaem.
- Skrytyy #1: Ashbi — myagkie otkazy, nikakikh setevykh zavisimostey; mozhno gonyat po cron/systemd.
- Skrytyy #2: Cover & Thomas — sozdaem rovno nuzhnye artefakty: JSON/MD/HTML + outbox.

Zemnoy abzats (inzheneriya):
Zapuskat raz v den/chas. Kontekst zabot beretsya iz fayla ili iz pamyati (kartochki s tegami chat/dialog/concern).
Rezultat — obnovlennyy portal i `portal/advice.md`.

# c=a+b
"""
from __future__ import annotations
import argparse, subprocess, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    ap = argparse.ArgumentParser(description="Daily advisor job")
    ap.add_argument("--context", default="", help="Fayl s tekstom zabot (opts.)")
    args = ap.parse_args()

    cmd = [sys.executable, "tools/u1_advisor.py"]
    if args.context:
        cmd += ["--context", args.context]
    subprocess.run(cmd, check=False)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())