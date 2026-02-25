# -*- coding: utf-8 -*-
"""listeners/usb_pkg_scanner.py - fonovyy scanner USB-paketov (optsionalno, po ENV).

Behavior:
  • Raz v PKG_SCAN_INTERVAL sekund scaniruet vse USB toma (modules.usb.recovery.list_usb_targets).
  • Ischet ZIP v ESTER/packages/, logiruet kolichestvo.
  • Esli PKG_AUTO_IMPORT=1 i PKG_IMPORTER_ENABLE=1 - pytaetsya verify+import (mode=merge).
  • Bezopasnost: pri lyubom sboe - tolko log, bez padeniya protsessa.

AB: odinakovo bezopasen v A/B (auto-import vypolnitsya tolko v B).

Mosty:
- Yavnyy (Ekspluatatsiya ↔ UX): avtomaticheskaya signalizatsiya o naydennykh paketakh.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): verify pered import, zhurnal priemki.
- Skrytyy 2 (Praktika ↔ Sovmestimost): vyklyucheno po umolchaniyu; offlayn i drop-in.

Zemnoy abzats:
Eto "dezhurnyy priemschik": uvidel paket na fleshke - proveril plombu i mozhet akkuratno prinyat (esli razresheno).

# c=a+b"""
from __future__ import annotations
import argparse, os, time
from modules.usb.recovery import list_usb_targets  # type: ignore
from modules.pack.packager import scan_usb_packages, verify_package, import_package  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB package scanner")
    ap.add_argument("--loop", action="store_true")
    args = ap.parse_args(argv)

    if not bool(int(os.getenv("PKG_IMPORTER_ENABLE","0"))):
        print("[pkg-scanner] disabled", flush=True)
        return 0

    iv = max(5, int(os.getenv("PKG_SCAN_INTERVAL","15")))
    auto = bool(int(os.getenv("PKG_AUTO_IMPORT","0")))

    try:
        while True:
            usb = list_usb_targets() or []
            mounts = [i.get("mount") for i in usb if i.get("mount")]
            found = scan_usb_packages(mounts).get("items", [])
            print(f"[pkg-scan] found={len(found)}", flush=True)
            if auto and AB == "B":
                for it in found:
                    p = it.get("path")
                    v = verify_package(p)
                    if v.get("ok"):
                        rep = import_package(p, mode="merge")
                        print(f"[pkg-import] {p} -> {rep.get('ok')}", flush=True)
            if not args.loop: break
            time.sleep(iv)
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b