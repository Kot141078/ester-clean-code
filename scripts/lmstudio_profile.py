# -*- coding: utf-8 -*-
"""scripts/lmstudio_profile.py - CLI-obertka dlya avto-profilya LM Studio/Ollama.

Primery:
  python -m scripts.lmstudio_profile
  python -m scripts.lmstudio_profile --base http://127.0.0.1:1234 --model my-7b --timeout 3.0

Mosty:
- Yavnyy (Logika ↔ Praktika): odin CLI - i detekt, i bench, i vyvod JSON dlya payplayna.
- Skrytyy 1 (Infoteoriya ↔ Diagnostika): pechataem tolko poleznuyu svodku; bez "water".
- Skrytyy 2 (Ashbi ↔ Upravlenie): A/B cherez ENV AB_MODE pozvolyaet bezopasno menyat nagruzku.

Zemnoy abzats:
Eto instrument mekhanika: quickly proverit “viden whether server i skolko on vydaet tokenov/sek”.
Udobno avtomatizirovat pri pervom zapuske uzla i v planirovschike.

# c=a+b"""
from __future__ import annotations

import argparse
import json
from typing import Optional

from modules.selfmanage.lmstudio_probe import bench_model, probe_and_bench, probe_summary  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Ester LM Studio Profile CLI")
    ap.add_argument("--base", type=str, default=None, help="BASE URL of OpenAI-compatible API (if known)")
    ap.add_argument("--model", type=str, default=None, help="Model name to check (if known)")
    ap.add_argument("--timeout", type=float, default=2.0, help="Request timeout, sec")
    ap.add_argument("--bench", action="store_true", help="Prinuditelno vypolnit bench")
    args = ap.parse_args(argv)

    if args.base and args.model:
        rep = {"ok": True, "candidates": [{"base_url": args.base, "bench": {"model": args.model, **bench_model(args.base, args.model, timeout=args.timeout)}}]}
    elif args.bench:
        rep = probe_and_bench(timeout=args.timeout)
    else:
        rep = probe_summary(timeout=args.timeout)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())