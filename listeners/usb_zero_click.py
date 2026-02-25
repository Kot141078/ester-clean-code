# -*- coding: utf-8 -*-
from __future__ import annotations

"""listeners/usb_zero_click.py - watcher Zero-Click: trustennaya fleshka → deploy.

Error from loga:
  expected an indented block after 'if' statement
Prichina: v kontse fayla bylo `if __name__ == "__main__":` bez tela (main zakommentirovan).

What was done:
- Ispravlen __main__ (raise SystemExit(main())).
- Ubrany krakozyabry v help/commentariyakh (UTF-8).
- Add flag --once (odin prokhod bez beskonechnogo tsikla) ​​— udobno dlya testa.
- Added zaschita ot sluchaynogo vklyucheniya: esli ESTER_USB_ZEROCLICK != "1",
  watcher ne startuet, krome sluchaya zapuska s --force.
- Logika idempotency sokhranena: in-memory cache mount->fingerprint.id, povtor podavlyaetsya do change id.
- Myagkiy fallback sys.path, esli fayl gruzyat kak odinochku (chtoby modules.* importy zhili).

Mosty (demand):
- Yavnyy most (Bezopasnost ↔ Orkestratsiya): tolko trustennye nositeli idut v avtodeploy.
- Skrytye mosty:
  1) Infoteoriya ↔ Diagnostika: fingerprint sostoyaniya nositelya - minimalnyy signal dlya podavleniya povtorov.
  2) Praktika ↔ Sovmestimost: edinyy put deploya cherez deploy_from_mount (odin “shlyuz”).

ZEMNOY ABZATs: vnizu."""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional

# If this file is loaded as a single file (without a package), place the root project in the sys.path
if __package__ in (None, ""):  # pragma: no cover
    try:
        _here = Path(__file__).resolve()
        # ozhidaem: <root>/listeners/usb_zero_click.py
        _root = _here.parents[1]
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
    except Exception:
        pass

from modules.usb.usb_probe import list_targets  # type: ignore
from modules.usb.usb_trust_store import is_trusted, compute_fingerprint, settings as trust_settings  # type: ignore
from modules.usb.usb_portable_deploy import deploy_from_mount  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()


def _enabled_by_env() -> bool:
    return (os.getenv("ESTER_USB_ZEROCLICK") or "0").strip() == "1"


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Ester Zero-Click USB watcher")
    ap.add_argument("--interval", type=int, default=5, help="interval skanirovaniya (sek)")
    ap.add_argument("--once", action="store_true", help="one pass and exit (no loop)")
    ap.add_argument("--force", action="store_true", help="run even if ESTER_USB_ZEROSLICK!=1")
    args = ap.parse_args(argv)

    if not args.force and not _enabled_by_env():
        print("[zeroclick] disabled (set ESTER_USB_ZEROCLICK=1 or run with --force)", flush=True)
        return 0

    interval = max(2, int(args.interval))
    print(f"[zeroclick] start: AB={AB}, interval={interval}, settings={trust_settings()}", flush=True)

    seen: Dict[str, str] = {}  # mount -> fingerprint.id (podavlenie povtorov)

    def one_pass() -> None:
        for dev in (list_targets() or []):
            try:
                mount = (dev or {}).get("mount")
                if not mount:
                    continue

                ok, _meta = is_trusted(mount)
                if not ok:
                    continue

                fp = compute_fingerprint(mount) or {}
                if not fp.get("ok"):
                    continue

                new_id = str(fp.get("id", "")).strip()
                if not new_id:
                    continue

                if seen.get(mount) == new_id:
                    continue  # have already handled this condition

                dry = (AB != "B")
                rep = deploy_from_mount(mount, profile_id=None, dry=dry) or {}
                print(
                    f"[zeroclick] deploy: mount={mount} dry={dry} ok={rep.get('ok')} notes={rep.get('notes')}",
                    flush=True,
                )
                seen[mount] = new_id
            except Exception as e:
                print(f"[zeroclick] device error: {e}", file=sys.stderr, flush=True)

    if args.once:
        one_pass()
        return 0

    while True:
        try:
            one_pass()
        except Exception as e:
            print(f"[zeroclick] loop error: {e}", file=sys.stderr, flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())


ZEMNOY = """ZEMNOY ABZATs (anatomiya/inzheneriya):
Eto “dezhurnyy na vkhode”: uvidel znakomyy beydzh (trusted USB) — propuskaet i provodit do “sklada”
bez vyzova operatora. No lyuboy vkhod dolzhen imet predokhranitel: poetomu AB_MODE (A=sukho),
i flazhok ESTER_USB_ZEROCLICK=1, chtoby sluchayno ne vklyuchit avtodeploy ot lyubogo zapuska."""