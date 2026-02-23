# -*- coding: utf-8 -*-
"""
listeners/usb_deploy_watcher.py — fonovye skan i avtodeploy s doverennykh fleshek.

Povedenie:
  • Kazhdye interval sek prosmatrivaem list_targets().
  • Dlya kazhdogo toma vyzyvaem apply_deploy(); v AB=A — tolko plan.
  • Logi pishutsya v usb_deploy_log.jsonl; zaschita ot povtorov — v usb_deploy_stamps.json.

ENV/CFG:
  • USB_DEPLOY_ENABLE=0|1
  • USB_DEPLOY_INTERVAL=10
  • AB_MODE=A|B

Mosty:
- Yavnyy (Ekspluatatsiya ↔ Bezopasnost): zero-click pri soblyudenii doveriya, okna vremeni i versii.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): logi i shtampy na diske; vosproizvodimost.
- Skrytyy 2 (Praktika ↔ Sovmestimost): dry-run cherez AB; modulnyy drop-in.

Zemnoy abzats:
Eto «dezhurnyy ustanovschik»: zamechaet svoyu fleshku, sveryaet vse po bumazhkam i akkuratno kladet novyy reliz.

# c=a+b
"""
from __future__ import annotations

import argparse, os, time
from modules.usb.usb_deploy_settings import load_deploy_settings  # type: ignore
from modules.usb.usb_deploy import scan_and_apply_all  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _enabled() -> bool:
    try:
        s = load_deploy_settings()
        return bool(s.get("enable"))
    except Exception:
        return False

def _interval() -> int:
    try:
        s = load_deploy_settings()
        return max(3, int(s.get("interval", 10)))
    except Exception:
        return 10

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB Zero-Click Deploy watcher")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=0)
    args = ap.parse_args(argv)

    if not _enabled():
        print("[usb-deploy] disabled", flush=True)
        return 0

    iv = int(args.interval or _interval())
    try:
        while True:
            scan_and_apply_all(ab_mode=AB)
            if not args.loop: break
            time.sleep(iv)
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b