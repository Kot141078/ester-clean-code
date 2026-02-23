# -*- coding: utf-8 -*-
from __future__ import annotations

"""listeners/usb_zt_agent_v2.py — CLI Zero‑Touch agent (once/loop) bez UI/HTTP.

Log-oshibka:
  expected an indented block after 'if' statement
Prichina: v kontse fayla bylo
  if __name__ == "__main__":
  # raise SystemExit(main())
to est blok __main__ bez tela.

Chto sdelano:
- Ispravlen __main__ (raise SystemExit(main())).
- Pochischeny “krakozyabry” v help-strokakh (UTF‑8).
- Sovmestimost zapuska kak fayla i kak modulya: dobavlen myagkiy sys.path fallback.
- Tipy sdelany sovmestimymi (bez list[str] i bez |, chtoby ne upiratsya v versiyu Python).

Mosty (trebovanie):
- Yavnyy most: usb_agent_core (scan/handle/loop) → CLI agent → fizicheskoe deystvie (deploy/recover) pod AB_MODE.
- Skrytye mosty:
  1) Kibernetika ↔ ekspluatatsiya: AB_MODE=A = “tolko plan”, AB_MODE=B = “vypolnenie”.
  2) Inzheneriya ↔ nadezhnost: zapusk kak modul/skript ne lomaet importy (minimum tochek otkaza).

ZEMNOY ABZATs: vnizu.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

# Esli fayl gruzyat kak odinochku (bez paketa), podlozhim project-root v sys.path
if __package__ in (None, ""):  # pragma: no cover
    try:
        _here = Path(__file__).resolve()
        # ozhidaem: <root>/listeners/usb_zt_agent_v2.py
        _root = _here.parents[1]
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
    except Exception:
        pass

# core (edinaya logika)
from modules.listeners.usb_agent_core import scan_once, handle_mount, loop  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Ester Zero‑Touch USB Agent v2")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true", help="odin prokhod (skan + obrabotka) i vykhod")
    g.add_argument("--loop", action="store_true", help="beskonechnyy tsikl")
    ap.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("ESTER_USB_SCAN_INTERVAL", "5")),
        help="interval skanirovaniya (sek)",
    )
    ap.add_argument(
        "--mount",
        default="",
        help="ogranichit obrabotku ukazannoy tochkoy montirovaniya (mount path)",
    )
    args = ap.parse_args(argv)

    target_mount = (args.mount or None)

    if args.once:
        scan = scan_once(target_mount=target_mount)
        out = {"ok": True, "ab": AB, "scan": scan}

        # srazu obrabatyvaem kandidatov v sootvetstvii s AB
        results = []
        for it in (scan.get("candidates") or []):
            try:
                m = (it or {}).get("mount")
                if not m:
                    continue
                results.append(handle_mount(m, dry=(AB != "B")))
            except Exception as e:
                results.append({"ok": False, "error": str(e)})
        out["results"] = results

        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    rep = loop(interval_sec=max(2, int(args.interval)), target_mount=target_mount)
    print(json.dumps({"ok": True, "ab": AB, "report": rep}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Zero‑Touch agent — eto kak dezhurnyy elektrik v nochnuyu smenu: on ne rassuzhdaet, on proveryaet linii
i vypolnyaet instruktsii. No u khoroshego elektrika est rezhim “tolko testerom” (AB_MODE=A),
i rezhim “vklyuchaem rubilnik” (AB_MODE=B). Bez takogo tumblera odna oshibka prevraschaetsya v pozhar.
"""