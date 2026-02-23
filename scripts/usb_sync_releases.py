# -*- coding: utf-8 -*-
"""
scripts/usb_sync_releases.py — utilita sinkhronizatsii relizov s USB.

Primery:
  python -m scripts.usb_sync_releases               # avto-poisk USB, pull v lokalnoe khranilische
  python -m scripts.usb_sync_releases --mount /media/owner/USB --push  # dvustoronnyaya sinkhronizatsiya
"""

from __future__ import annotations

import argparse
import json

from modules.selfmanage.usb_sync import sync
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Sync Ester releases with USB")
    p.add_argument(
        "--mount", type=str, default=None, help="Tochka montirovaniya USB"
    )
    p.add_argument(
        "--push",
        action="store_true",
        help="Pushit lokalnye arkhivy na USB (po umolchaniyu tolko pull)",
    )
    a = p.parse_args(argv)

    rep = sync(usb_mount=a.mount, push_to_usb=a.push)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if rep.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())