# -*- coding: utf-8 -*-
"""scripts/transport_ping.py - CLI ping uzla po HTTP.

Primer:
  python -m scripts.transport_ping --base http://192.168.1.20:8080

Mosty:
- Yavnyy (Svyaz ↔ Diagnostika): bystryy otvet “zhiv?” dlya lyubykh avtomatizatsiy.
- Skrytyy 1 (Infoteoriya ↔ CLI): strogiy JSON — goditsya v payplayny.
- Skrytyy 2 (Praktika ↔ Bezopasnost): X-Ester-Cluster pri nalichii sekreta.

Zemnoy abzats:
Obychnyy “ping po prilozheniyu”: proveryaet, dostupen li /ops/ping na udalennom uzle.

# c=a+b"""
from __future__ import annotations

import argparse
import json
from modules.transport.transport_manager import http_ping  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ester HTTP ping")
    ap.add_argument("--base", required=True, help="Bazovyy URL uzla (http://host:port)")
    args = ap.parse_args(argv)
    rep = http_ping(args.base)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())