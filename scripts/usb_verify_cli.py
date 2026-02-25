# -*- coding: utf-8 -*-
"""scripts/usb_verify_cli.py - CLI-verify fleshki Ester.

Primer:
  python -m scripts.usb_verify_cli --mount /media/USB

Vyvodit strogiy JSON otchet (sm. modules.selfmanage.usb_verify.verify_usb).

Mosty:
- Yavnyy (Svyaz ↔ Ekspluatatsiya): tot zhe otchet, chto i v UI, dlya avtomatizatsiy/CI.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): sverka sha256/nalichiya v terminale, bez storonnikh tulov.
- Skrytyy 2 (Praktika ↔ Bezopasnost): read-only, bez zapisi na nositel.

Zemnoy abzats:
Udobno dlya “sukhogo dopuska” — proverit fleshku avtomaticheski pered vydachey v rabotu.

# c=a+b"""
from __future__ import annotations

import argparse
import json
from modules.selfmanage.usb_verify import verify_usb  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB Verify CLI")
    ap.add_argument("--mount", required=True, help="USB mount point")
    args = ap.parse_args(argv)
    rep = verify_usb(args.mount)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())