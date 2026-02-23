# -*- coding: utf-8 -*-
"""
scripts/make_usb_headless.py — headless: sobrat reliz (opts.) i zapisat /ESTER na ukazannyy tom.

Primery:
  python -m scripts.make_usb_headless --mount /media/USB --with-release --label ESTER_USB
  python -m scripts.make_usb_headless --mount E:\\ --with-release --with-dump D:\\dump.tar.gz --dry

Mosty:
- Yavnyy (Kibernetika ↔ Orkestratsiya): odin vyzov — vsya tsepochka.
- Skrytyy 1 (Infoteoriya ↔ Kontrakty): ta zhe logika, chto v UI, bez dublirovaniya API.
- Skrytyy 2 (Praktika ↔ Bezopasnost): dry-run po umolchaniyu cherez AB_MODE=A.

Zemnoy abzats:
Udobno v stsenariyakh bez brauzera i na CI-stankakh: sdelat fleshku odnoy komandoy.

# c=a+b
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from modules.packaging.release_builder import build_release_archive  # type: ignore
from modules.selfmanage.usb_writer import write_usb  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB Maker (headless)")
    ap.add_argument("--mount", required=True, help="put montirovaniya USB")
    ap.add_argument("--with-release", action="store_true", help="sobrat i dobavit arkhiv reliza")
    ap.add_argument("--with-dump", type=str, default="", help="put k dampu dlya dobavleniya")
    ap.add_argument("--label", type=str, default=os.getenv("ESTER_USB_LABEL", "ESTER"))
    ap.add_argument("--dry", action="store_true", help="ne zapisyvat (tolko sobrat/splanirovat)")
    args = ap.parse_args(argv)

    archive_path = None
    build_report = None
    if args.with_release:
        out_dir = Path(".").resolve() if (args.dry or AB != "B") else Path(args.mount).resolve()
        build_report = build_release_archive(output_dir=str(out_dir), include_dump=(args.with_dump or None))
        if not build_report.get("ok"):
            print(json.dumps({"ok": False, "error": "build-failed", "report": build_report}, ensure_ascii=False, indent=2))
            return 2
        archive_path = build_report.get("archive")

    if args.dry or AB != "B":
        print(json.dumps({"ok": True, "dry": True, "mount": args.mount, "label": args.label, "archive": archive_path, "dump": (args.with_dump or None), "build": build_report}, ensure_ascii=False, indent=2))
        return 0

    rep = write_usb(mount=args.mount, from_archive=archive_path, from_dump=(args.with_dump or None), label=args.label)
    print(json.dumps({"ok": bool(rep.get("ok")), "write_report": rep, "build": build_report}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())