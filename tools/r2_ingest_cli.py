#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R2/tools/r2_ingest_cli.py - edinyy CLI dlya ingensta RSS i papki inbox.

Mosty:
- Yavnyy: Enderton - komandy CLI kak predikaty (rss-pull | inbox-scan) nad parametrami.
- Skrytyy #1: Ashbi — prostoy regulyator: lineynoe vypolnenie, bez fonovykh tredov/demonov.
- Skrytyy #2: Cover & Thomas — minimalnyy “signal” (kratkie svodki) snizhaet neopredelennost pri priemke.

Zemnoy abzats:
Komandy:
  rss-pull - `--url` (http/https/file), `--user`, `--tag`
  inbox-scan - `--dir`, `--user`, `--tag`, `--pattern` (by default *.txt;*.md;*.html)
Rabotaet tolko na stdlib. No problem. Pishet kartochki v `PERSIST_DIR/ester_cards.json`.

# c=a+b"""
from __future__ import annotations
import argparse
import json
import os
import sys

from services.ingest.rss_ingestor import ingest_rss  # type: ignore
from services.ingest.file_ingestor import inbox_scan  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)

def main() -> int:
    ap = argparse.ArgumentParser(description="R2 ingest CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_rss = sub.add_parser("rss-pull", help="Zagruzit RSS/Atom i dobavit v pamyat (CardsMemory)")
    p_rss.add_argument("--url", required=True, help="URL (http/https/file)")
    p_rss.add_argument("--user", default=os.getenv("ESTER_USER", "Owner"))
    p_rss.add_argument("--tag", default="rss")

    p_inb = sub.add_parser("inbox-scan", help="Scan local folder and add to memory")
    p_inb.add_argument("--dir", default=os.getenv("INBOX_DIR") or os.path.abspath(os.path.join(os.getcwd(), "inbox")))
    p_inb.add_argument("--user", default=os.getenv("ESTER_USER", "Owner"))
    p_inb.add_argument("--tag", default="inbox")
    p_inb.add_argument("--pattern", default="*.txt;*.md;*.markdown;*.html;*.htm")

    args = ap.parse_args()
    if args.cmd == "rss-pull":
        res = ingest_rss(args.url, user=args.user, tag=args.tag)
        print(_j(res))
        return 0
    if args.cmd == "inbox-scan":
        res = inbox_scan(root=args.dir, user=args.user, tag=args.tag, pattern=args.pattern)
        print(_j(res))
        return 0
    return 0

if __name__ == "__main__":
    raise SystemExit(main())