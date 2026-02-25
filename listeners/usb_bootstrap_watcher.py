# -*- coding: utf-8 -*-
"""listeners/usb_bootstrap_watcher.py - vakhter USB: ischet “almost empty” fleshki i predlagaet One-Click Bootstrap cherez Hot-Ask.

Logika:
  • Periodicheski skaniruem montirovaniya (modules.portable.env.find_usb_mounts).
  • Dlya kazhdoy fleshki schitaem “pustotu” (modules.portable.emptiness.is_near_empty).
  • Esli empty i esche ne predlagali – shlem v Hot-Ask pending: action=offer_oneclick.
  • Repeat ne spamim: remember predlozhennye mounts do razmontirovaniya.

ENV:
  USB_BOOTSTRAP_ENABLE=1
  USB_BOOTSTRAP_POLL_SEC=20

Mosty:
- Yavnyy (Obnaruzhenie ↔ Deystvie): avtomaticheskiy translation “pustaya fleshka” → “predlozhit podgotovku”.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): logi v hotask_state, bez skrytykh said-effektov.
- Skrytyy 2 (Praktika ↔ Sovmestimost): offlayn, stdlib; dry-rezhim cherez AB.

Zemnoy abzats:
Kak master-priemschik: uvidel novyy pustoy nositel — predlozhil razlozhit po polochkam.

# c=a+b"""
from __future__ import annotations
import argparse, json, os, time
from pathlib import Path
from typing import Set
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _find_mounts():
    try:
        from modules.portable.env import find_usb_mounts  # type: ignore
        return [str(p) for p in find_usb_mounts()]
    except Exception:
        return []

def _is_near_empty(p: str) -> bool:
    try:
        from modules.portable.emptiness import is_near_empty  # type: ignore
        return is_near_empty(Path(p))
    except Exception:
        return False

def _offer(mount: str):
    try:
        from modules.portable.hotask_state import add_pending  # type: ignore
        from modules.env.presets import recommend_profile      # type: ignore
        payload = {"mount": mount, "action": "offer_oneclick", "profile": recommend_profile()}
        if AB == "B":
            add_pending("offer_oneclick", payload)
        return {"ok": True, "dry": AB != "B", "payload": payload}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB Bootstrap Watcher")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--period", type=int, default=int(os.getenv("USB_BOOTSTRAP_POLL_SEC","20")))
    args = ap.parse_args(argv)

    if os.getenv("USB_BOOTSTRAP_ENABLE","1") != "1":
        print(json.dumps({"ts": int(time.time()), "mod":"usb_bootstrap_watcher", "status":"disabled"}), flush=True)
        return 0

    known: Set[str] = set()
    try:
        while True:
            mounts = _find_mounts()
            now_known = set(mounts)
            for m in mounts:
                if m in known:
                    continue
                if _is_near_empty(m):
                    res = _offer(m)
                    print(json.dumps({"ts": int(time.time()), "mod":"usb_bootstrap_watcher", "mount": m, "offer": res}), flush=True)
                    known.add(m)
            # sbrosit demontirovannye
            known = {k for k in known if k in now_known}
            if not args.loop: break
            time.sleep(max(3, int(args.period)))
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b