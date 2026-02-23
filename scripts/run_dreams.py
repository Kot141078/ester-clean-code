# -*- coding: utf-8 -*-
"""
scripts/run_dreams.py — CLI dlya zapuska «Snov 2.0» (klasterizatsiya flashback → HypothesisStore → KG).

Primery:
  python -m scripts.run_dreams --rules config/dreams_rules.yaml --json
  PERSIST_DIR=./data python scripts/run_dreams.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from modules.dreams_engine import DreamRule, DreamsEngine  # drop-in
from modules.ingest.common import build_mm_from_env  # kanonnyy bilder memory manager
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _load_rules(path: str) -> list[DreamRule]:
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None

    if not path or not os.path.exists(path) or yaml is None:
        # Esli konfiga net, vozvraschaem defoltnoe pravilo
        return [DreamRule()]

    try:
        # Yavno ukazyvaem utf-8, chtoby konfig pravil tozhe chitalsya korrektno
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        rules_raw = data.get("rules") if isinstance(data, dict) else []
        rules: list[DreamRule] = []
        
        for r in rules_raw or []:
            rules.append(
                DreamRule(
                    query=str(r.get("query") or "*"),
                    k=int(r.get("k") or 200),
                    ngram=int(r.get("ngram") or 3),
                    min_cluster_size=int(r.get("min_cluster_size") or 2),
                    max_hypotheses_per_cluster=int(r.get("max_hypotheses_per_cluster") or 2),
                )
            )
        return rules or [DreamRule()]
    except Exception:
        # Fallback pri oshibke parsinga
        return [DreamRule()]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run Dreams 2.0")
    p.add_argument(
        "--rules",
        type=str,
        default=os.getenv("DREAM_RULES", "config/dreams_rules.yaml"),
    )
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    # Initsializatsiya pamyati (Memory Stack)
    mm = build_mm_from_env()
    engine = DreamsEngine(mm, provider=None)
    
    # Zapusk protsessa snovideniy (Deep Thinking / Clustering)
    report = engine.run(_load_rules(a.rules))

    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"OK: clusters={report['clusters']} hypotheses={report['hypotheses']} saved={report['saved']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())