# -*- coding: utf-8 -*-
"""scripts/first_run_headless.py - headless-obertka mastera pervogo zapuska.

Primery:
  python -m scripts.first_run_headless --bench --start-agent --headless

Mosty:
- Yavnyy (Kibernetika ↔ Orkestratsiya): odin vyzov obedinyaet osmotr khosta, bench i zapusk agenta.
- Skrytyy 1 (Infoteoriya ↔ Diagnostika): pechataem strogiy JSON-otchet (goditsya v CI/installyatorakh).
- Skrytyy 2 (Praktika ↔ Bezopasnost): vse po yavnoy komande; nikakikh skrytykh servisov.

Zemnoy abzats:
Udobno dlya “sukhogo” razvertyvaniya bez brauzera: razovo startanut agenta i ponyat, chto vidno iz korobki.

# c=a+b"""
from __future__ import annotations

import argparse
import json
from modules.wizard.first_run import apply_autosetup  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ester First-Run (headless)")
    ap.add_argument("--bench", action="store_true", help="vypolnit korotkiy bench LM Studio")
    ap.add_argument("--start-agent", action="store_true", help="launch USB agent (current session)")
    ap.add_argument("--headless", action="store_true", help="bez sistemnykh uvedomleniy")
    args = ap.parse_args(argv)

    rep = apply_autosetup(bench=args.bench, start_agent=args.start_agent, headless=args.headless)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())