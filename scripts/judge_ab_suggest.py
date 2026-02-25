# -*- coding: utf-8 -*-
"""scripts/judge_ab_suggest.py - pechat podskazok A/B dlya Judge (JSON).

Primery:
  python -m scripts.judge_ab_suggest
  python -m scripts.judge_ab_suggest --bench

Mosty:
- Yavnyy (Kibernetika ↔ Orkestratsiya): odin vyzov — vsya svodka slotov.
- Skrytyy 1 (Infoteoriya ↔ CLI): vydaem strogiy JSON dlya payplaynov.
- Skrytyy 2 (Bayes ↔ Bezopasnost): slotB traktuem kak eksperiment.

Zemnoy abzats:
Instrument dlya avtomaticheskoy sborki “kandidatov” slotov na lyubom uzle bez UI/brauzera.

# c=a+b"""
from __future__ import annotations

import argparse
import json
from modules.judge.ab_suggest import build_suggestion, suggestion_to_dict  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ester Judge A/B Suggest")
    ap.add_argument("--bench", action="store_true", help="vypolnit korotkiy bench modeley")
    args = ap.parse_args(argv)

    s = build_suggestion(bench=args.bench)
    print(json.dumps(suggestion_to_dict(s), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())