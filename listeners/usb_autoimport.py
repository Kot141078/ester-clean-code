# -*- coding: utf-8 -*-
"""listeners/usb_autoimport.py - listener avto-importa nastroek s trusted fleshki.

Rezhimy:
  • once (po umolchaniyu) - odin prokhod scanirovaniya.
  • --loop — tsikl: skanirovat kazhdye --interval sek.

Otklyuchaemo cherez ENV:
  • USB_AUTOIMPORT_ENABLE=0|1 (by default 0)
  • USB_AUTOIMPORT_INTERVAL=10

Mosty:
- Yavnyy (Orkestratsiya ↔ Ekspluatatsiya): avtonomnyy vorker, kotoryy “podbiraet” nastroyki s doverennykh fleshek.
- Skrytyy 1 (Infoteoriya ↔ Diagnostika): kompaktnye logi i detailed JSON-otchety po kazhdomu tomu.
- Skrytyy 2 (Praktika ↔ Sovmestimost): ispolzuet list_targets() i compute_fingerprint() — uzhe prinyatyy kontrakt.

Zemnoy abzats:
Eto medsestra priemnogo otdeleniya: uvidela “svoyu” fleshku - akkuratno nanesla nastroyki, ne trogaya ostalnoe.

# c=a+b"""
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Dict, List

from modules.usb.usb_probe import list_targets  # type: ignore
from modules.usb.autoimport_settings import autoimport_from_mount  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _enabled() -> bool:
    return bool(int(os.getenv("USB_AUTOIMPORT_ENABLE", "0")))

def _interval() -> int:
    try:
        return max(3, int(os.getenv("USB_AUTOIMPORT_INTERVAL", "10")))
    except Exception:
        return 10

def _scan_once() -> List[Dict]:
    rep = []
    tg = list_targets()
    for t in tg:
        mnt = (t.get("mount") or "").strip()
        if not mnt:
            continue
        r = autoimport_from_mount(mnt, ab_mode=AB)
        if r.get("ok") or r.get("reason") not in ("no-fingerprint","manifest-missing","backup-not-found","no-mode","not-trusted"):
            rep.append({"mount": mnt, "result": r})
    return rep

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB auto-import listener")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=0)
    args = ap.parse_args(argv)

    if not _enabled():
        print("[usb-autoimport] disabled", flush=True)
        return 0

    iv = int(args.interval or _interval())
    try:
        while True:
            res = _scan_once()
            if res:
                print(json.dumps({"ab": AB, "scan": res}, ensure_ascii=False), flush=True)
            if not args.loop:
                break
            time.sleep(iv)
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b