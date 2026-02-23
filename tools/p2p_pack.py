# -*- coding: utf-8 -*-
"""
CLI — upakovka P2P payload iz lokalnoy ocheredi.

Most (yavnyy):
- (CLI ↔ UI) Ekvivalent deystviya «Sobrat iz ocheredi» v adminke.

Mosty (skrytye):
- (Infoteoriya ↔ Ekonomika) Kanonizatsiya JSON → stabilnye kheshi → menshe lozhnykh dubley.
- (Nadezhnost ↔ Operatsii) Dry-run po umolchaniyu snizhaet risk neozhidannykh zapisey.

Zemnoy abzats:
Komanda sobiraet JSON-paket zadach iz `ESTER/state/queue` v `ESTER/p2p/outbox` i (opts.) kopiruet v `LAN_DROP_DIR/p2p`.

# c=a+b
"""
from __future__ import annotations

import argparse
import os
import json

from modules.p2p.filemesh import pack_from_queue
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()

def main():
    ap = argparse.ArgumentParser(description="P2P pack from local queue (A/B).")
    ap.add_argument("--limit", type=int, default=50, help="Skolko zadach upakovat (po mtime)")
    ap.add_argument("--no-lan", action="store_true", help="Ne kopirovat v LAN_DROP_DIR/p2p")
    args = ap.parse_args()

    res = pack_from_queue(limit=args.limit, also_copy_to_lan=(not args.no_lan))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res.get("ok"):
        print(f"[OK] AB={AB_MODE} pack: written={res.get('written')} hash={res.get('preview',{}).get('hash')}")

if __name__ == "__main__":
    raise SystemExit(main())
