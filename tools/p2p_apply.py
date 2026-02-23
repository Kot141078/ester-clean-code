# -*- coding: utf-8 -*-
"""
CLI — import P2P payload’ov iz inbox (i opts. sink iz LAN).

Most (yavnyy):
- (CLI ↔ UX) Prostaya komanda «primenit» otrazhaet tu zhe operatsiyu v UI.

Mosty (skrytye):
- (Infoteoriya ↔ Nadezhnost) Indeksy payload/item-kheshey delayut import idempotentnym.
- (Formaty ↔ Ekspluatatsiya) Chistyy stdlib — menshe zavisimostey na mashinakh-uchastnikakh.

Zemnoy abzats:
Komanda (v A — prevyu) importiruet `*.json` iz `ESTER/p2p/inbox/` (i pri neobkhodimosti kopiruet iz `LAN_DROP_DIR/p2p/`)
v lokalnuyu ochered `ESTER/state/queue/*.json` i pomechaet iskhodnyy payload kak `.done`.

# c=a+b
"""
from __future__ import annotations

import argparse
import os
import json

from modules.p2p.filemesh import discover, sync_lan_inbox, apply_inbox
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()

def main():
    ap = argparse.ArgumentParser(description="P2P apply from inbox (A/B).")
    ap.add_argument("--scan", action="store_true", help="Pokazat sostoyanie (bez izmeneniy)")
    ap.add_argument("--apply", action="store_true", help="Importirovat payload’y iz inbox (ispolzuet A/B)")
    ap.add_argument("--no-lan", action="store_true", help="Ne kopirovat predvaritelno iz LAN_DROP_DIR/p2p")
    ap.add_argument("--max", type=int, default=20, help="Maksimum faylov k primeneniyu za raz")
    args = ap.parse_args()

    if args.scan or not (args.scan or args.apply):
        snap = discover()
        print(json.dumps(snap, ensure_ascii=False, indent=2))
        print(f"[OK] AB={AB_MODE} scan: inbox={len(snap.get('inbox', []))}, outbox={len(snap.get('outbox', []))}")
        return

    if not args.no_lan:
        print(json.dumps(sync_lan_inbox(), ensure_ascii=False, indent=2))

    res = apply_inbox(max_files=args.max)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res.get("ok"):
        print(f"[OK] AB={AB_MODE} apply: payloads={res.get('applied_payloads')} items={res.get('applied_items')}")

if __name__ == "__main__":
    raise SystemExit(main())
