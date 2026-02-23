#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilita replikatsii (dry-run):
- Beret spisok pirov iz REPLICATION_PEERS ili --peer
- Podtyagivaet /replication/snapshot, proveryaet X-Signature (HMAC)
- V dry-run nichego ne primenyaet; vozvraschaet 0 pri uspeshnoy validatsii khotya by odnogo pira
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List

import requests

from security.signing import hmac_verify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def parse_peers(env: str) -> List[str]:
    return [p.strip() for p in (env or "").split(",") if p.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--peer", action="append", help="peer base url")
    ap.add_argument("--token", default=os.getenv("REPLICATION_TOKEN", ""))
    ap.add_argument("--dry-run", action="store_true", default=True)
    args = ap.parse_args()

    peers = args.peer or parse_peers(os.getenv("REPLICATION_PEERS", ""))
    if not peers:
        print("no peers provided", file=sys.stderr)
        return 1

    ok = 0
    for peer in peers:
        try:
            url = peer.rstrip("/") + "/replication/snapshot"
            headers = {"X-REPL-TOKEN": args.token} if args.token else {}
            r = requests.get(url, headers=headers, timeout=30)
            sig = r.headers.get("X-Signature", "")
            if not sig or not hmac_verify(r.content, sig):
                print(f"[{peer}] bad signature", file=sys.stderr)
                continue
            print(f"[{peer}] snapshot OK ({len(r.content)} bytes)")
            ok += 1
        except Exception as e:
            print(f"[{peer}] error: {e}", file=sys.stderr)
    return 0 if ok > 0 else 2


if __name__ == "__main__":
    sys.exit(main())