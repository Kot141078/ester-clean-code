# -*- coding: utf-8 -*-
"""scripts/run_decay_gc.py - CLI dlya zapuska ubyvaniya vesov i GC grafa znaniy.

Primery:
  python -m scripts.run_decay_gc --json
  PERSIST_DIR=./data python scripts/run_decay_gc.py --half-life 432000 --edge-th 0.1 --json"""

from __future__ import annotations

import argparse
import json
import os
import sys

from memory.decay_gc import DecayGC, DecayRules  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run KG decay & GC")
    p.add_argument(
        "--half-life",
        type=float,
        default=float(os.getenv("GC_HALF_LIFE_S", 7 * 24 * 3600)),
    )
    p.add_argument("--min-weight", type=float, default=float(os.getenv("GC_MIN_WEIGHT", 0.05)))
    p.add_argument(
        "--edge-min-age",
        type=float,
        default=float(os.getenv("GC_EDGE_MIN_AGE_S", 2 * 24 * 3600)),
    )
    p.add_argument("--edge-th", type=float, default=float(os.getenv("GC_EDGE_WEIGHT_TH", 0.08)))
    p.add_argument(
        "--node-min-age",
        type=float,
        default=float(os.getenv("GC_NODE_MIN_AGE_S", 3 * 24 * 3600)),
    )
    p.add_argument("--json", action="store_true", help="Print a report in ZhSON")

    a = p.parse_args(argv)
    rules = DecayRules(
        half_life_s=a.half_life,
        min_weight=a.min_weight,
        gc_edge_min_age_s=a.edge_min_age,
        gc_edge_weight_threshold=a.edge_th,
        gc_node_min_age_s=a.node_min_age,
    )
    gc = DecayGC()
    report = gc.apply(rules)
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"OK: decayed_edges={report['decayed_edges']} removed_edges={report['removed_edges']} removed_nodes={report['removed_nodes']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())