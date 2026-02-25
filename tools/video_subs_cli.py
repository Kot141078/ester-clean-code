#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/video_subs_cli.py - CLI dlya proaktivnogo obkhoda podpisok/poiska video.

Primery:
  # Dry run (only show what was found):
  python tools/video_subs_cli.py --dry-run

  # Zapustit obrabotku podpisok:
  python tools/video_subs_cli.py --run

  # Search po topic (ytsearch):
  python tools/video_subs_cli.py --search "bayesian inference lecture" --limit 2

Optsii:
  --dry-run Show, kakie elementy budut obrabotany (bez ingest)
  --run Vypolnit obkhod podpisok (mode=subs)
  --search TOPIC Vypolnit ytsearch po topic (mode=search)
  --limit N Ogranichenie chisla elementov (po umolchaniyu 3)

Mosty:
- Yavnyy: (UX ↔ Operatsii) Operatoram udobno testirovat work bez UI/REST.
- Skrytyy #1: (Kibernetika ↔ Planirovschik) Ispolzuyte iz kron/planirovschika (s ENV VIDEO_SUBS_ENABLED=1).
- Skrytyy #2: (Inzheneriya ↔ Nadezhnost) Sukhoy progon snizhaet risk "zakhlebnutsya" ot bolshogo obema.

Zemnoy abzats:
Eto kak "ruchnoy obkhodchik" sklada: mozhno proyti bez pogruzki (dry-run), a mozhno zapustit pogruzchik (run).

# c=a+b"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List

from modules.proactive.video_autorunner import run_once  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--search", type=str, default="")
    ap.add_argument("--limit", type=int, default=3)
    args = ap.parse_args(argv)

    if args.dry_run:
        # dry-run: we will show which URLs will be collected from the configuration without causing ingest
        from modules.proactive.video_autorunner import _load_yaml, _ytsearch_to_url  # type: ignore
        cfg = _load_yaml(os.path.join("config", "video_subscriptions.yaml"))
        subs = [s for s in (cfg.get("subscriptions") or []) if int(s.get("enabled") or 0) == 1]
        out: Dict[str, Any] = {"mode": "subs", "urls": []}
        for s in subs:
            kind = str(s.get("kind") or "rss")
            lim = int(s.get("limit") or args.limit or 3)
            if kind == "rss":
                out["urls"].append({"id": s.get("id"), "rss": s.get("url"), "limit": lim})
            elif kind == "direct":
                out["urls"].append({"id": s.get("id"), "url": s.get("url")})
            elif kind == "ytsearch":
                out["urls"].append({"id": s.get("id"), "ytsearch": _ytsearch_to_url(str(s.get("query") or ""), lim)})
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.run:
        rep = run_once(mode="subs", topic=None, limit=args.limit)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0

    if args.search:
        rep = run_once(mode="search", topic=args.search, limit=args.limit)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0

    ap.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
