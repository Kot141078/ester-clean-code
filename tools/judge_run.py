# -*- coding: utf-8 -*-
"""
CLI — Judge: sobrat otvety i vydat finalku.

Most (yavnyy):
- (CLI ↔ UI) Ekvivalent odnoy knopki v adminke, udoben dlya skriptov.

Mosty (skrytye):
- (Nadezhnost ↔ Ekspluatatsiya) Strogiy format JSON-vykhoda uproschaet parsing i integratsiyu.
- (Infoteoriya ↔ Ekonomika) Unifikatsiya struktury otvetov umenshaet trenie mezhdu uzlami.

Zemnoy abzats:
Zapuskaet «sudyu»: v A — moki, v B — lokalnye LM Studio po alias iz recommend.env.
Finalka vybiraetsya majority/median. Logi pishutsya v ESTER/state/judge/* (tolko v B).

# c=a+b
"""
from __future__ import annotations

import argparse
import json
import os

from modules.judge.core import judge, MODE_LOCAL, MODE_FULL, MODE_FLEX
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()

def main():
    ap = argparse.ArgumentParser(description="Judge aggregator (A/B).")
    ap.add_argument("--prompt", required=True, help="Polzovatelskiy prompt")
    ap.add_argument("--mode", choices=[MODE_LOCAL, MODE_FULL, MODE_FLEX], default=MODE_LOCAL, help="Rezhim zaprosa")
    ap.add_argument("--timeout", type=float, default=6.0, help="Taymaut na odin endpoint")
    args = ap.parse_args()

    res = judge(args.prompt, mode=args.mode, timeout=args.timeout)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res.get("ok"):
        print(f"[OK] AB={AB_MODE} mode={args.mode} answers={len(res.get('answers', []))}")

if __name__ == "__main__":
    raise SystemExit(main())
