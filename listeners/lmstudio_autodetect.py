# -*- coding: utf-8 -*-
"""
listeners/lmstudio_autodetect.py — periodicheskiy zond LM Studio (/v1/models) i obnovlenie kesha.

Povedenie:
  • Kazhdye LMSTUDIO_PROBE_INTERVAL sekund vyzyvaet bridge.scan_endpoints().
  • V AB=A i AB=B odinakovo (zondirovanie bezopasno, bez generatsiy).
  • Logi lakonichnye.

ENV:
  LMSTUDIO_ENABLE=1     — vklyuchaet slushatelya
  LMSTUDIO_PROBE_INTERVAL=60

Mosty:
- Yavnyy (Integratsiya ↔ Kibernetika): podderzhivaem aktualnyy snimok dostupnykh modeley lokalno.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): kesh v JSON — proveryaemo i vosproizvodimo.
- Skrytyy 2 (Praktika ↔ Sovmestimost): drop-in; ne trebuet nalichiya LM Studio — prosto pishet «net svyazi».

Zemnoy abzats:
Eto «dezhurnyy skaner»: poglyadyvaet, zhiv li LM Studio ryadom, i kakie modeli dostupny — bez shuma.

# c=a+b
"""
from __future__ import annotations
import argparse, os, time
from modules.lmstudio.bridge import scan_endpoints  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester LM Studio autodetect")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=0)
    args = ap.parse_args(argv)

    if not bool(int(os.getenv("LMSTUDIO_ENABLE","0"))):
        print("[lmstudio] disabled", flush=True)
        return 0
    iv = max(10, int(args.interval or int(os.getenv("LMSTUDIO_PROBE_INTERVAL","60"))))
    try:
        while True:
            rep = scan_endpoints()
            print("[lmstudio-scan]", ("models="+str(len(rep.get("models",[]))) if rep.get("ok") else "fail"), flush=True)
            if not args.loop: break
            time.sleep(iv)
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b