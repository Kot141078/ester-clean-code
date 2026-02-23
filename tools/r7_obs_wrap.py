#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R7/tools/r7_obs_wrap.py — obertka komandy: zamer wall-time/RC i zapis metrik.

Mosty:
- Yavnyy: Enderton — predikaty uspekha: rc==0 ∧ wall_ms>=0; serializuem nablyudenie v jsonl.
- Skrytyy #1: Ashbi — regulyator prosche sistemy: lineynyy zapusk + taymer, bez lishney logiki.
- Skrytyy #2: Cover & Thomas — minimalnyy «signal»: tolko to, chto nuzhno dlya SLO (rc, ms, cmd).

Zemnoy abzats (inzheneriya):
Zapusk: `python tools/r7_obs_wrap.py -- <cmd...>`; metrika tipa "cmd" v `obs/metrics.jsonl`.
Bez vneshnikh zavisimostey, podkhodit dlya cron.

# c=a+b
"""
from __future__ import annotations
import argparse, os, shlex, subprocess, time
from services.obs.metrics import record, timer  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    ap = argparse.ArgumentParser(description="Wrap a command and record metrics")
    ap.add_argument("--tag", default="adhoc")
    ap.add_argument("sep", nargs="?", help="-- separator", default=None)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    if not args.cmd:
        print("usage: r7_obs_wrap.py -- <command...>")
        return 2

    cmdline = args.cmd
    t0 = time.time()
    try:
        proc = subprocess.run(cmdline, check=False)
        rc = proc.returncode
    except Exception as e:
        rc = -1

    wall_ms = (time.time() - t0) * 1000.0
    record("cmd", {"rc": rc, "ms": wall_ms, "cmd": cmdline, "tag": args.tag})
    print(f"[obs] rc={rc} ms={int(wall_ms)} cmd={' '.join(shlex.quote(x) for x in cmdline)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

# c=a+b