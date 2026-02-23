# -*- coding: utf-8 -*-
"""
scripts/experiments/offline_replay.py — offlayn-replay istorii sobytiy dlya obucheniya/metrik.

MOSTY:
- (Yavnyy) Zagruzhaet sobytiya, treniruet LearningManager, vyvodit deltu chisla obnovlennykh vesov i mini-svodku.
- (Skrytyy #1) Mozhno zapuskat po kronu — «poduchivat» sistemu offlayn raz v den.
- (Skrytyy #2) Porog since_ts pozvolyaet delat inkrementalnye progony.

ZEMNOY ABZATs:
Polezno dlya ekspluatatsii: prognat istoriyu za sutki, obnovit vesa i uvidet, gde modeli «doumilis».

# c=a+b
"""
from __future__ import annotations

import argparse
import time

from modules.synergy.learning import LearningManager
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", dest="team", default=None, help="team_id (esli ne ukazan — vse)")
    ap.add_argument("--since", dest="since", type=int, default=None, help="unix-ts, otkuda nachinat")
    args = ap.parse_args()

    lm = LearningManager.default()
    t0 = time.time()
    updated = lm.train_from_events(team_id=args.team, since_ts=args.since)
    t1 = time.time()
    ws = lm.list_weights()
    print(f"✓ updated={updated} weights in {t1-t0:.3f}s; total={len(ws)}")
    # pokazhem top-10 otklonivshikhsya ot 1.0
    ws = sorted(ws, key=lambda w: abs(w.weight-1.0), reverse=True)[:10]
    for w in ws:
        print(f"  {w.agent_id}/{w.role}: {w.weight:.3f} (n={w.n}, ts={w.updated_ts})")

if __name__ == "__main__":
    main()