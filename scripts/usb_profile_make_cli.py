# -*- coding: utf-8 -*-
"""
scripts/usb_profile_make_cli.py — headless-sborka /ESTER po profilyu.

Primer:
  AB_MODE=B python -m scripts.usb_profile_make_cli --profile-id <ID> --mount /media/USB
  AB_MODE=A python -m scripts.usb_profile_make_cli --profile-id <ID> --mount E:\\ --dry

Mosty:
- Yavnyy (Kibernetika ↔ Orkestratsiya): odna komanda — sobrat po sokhranennym nastroykam.
- Skrytyy 1 (Infoteoriya ↔ Kontrakty): ispolzuet suschestvuyuschie build_release_archive + write_usb.
- Skrytyy 2 (Praktika ↔ Bezopasnost): dry-run po umolchaniyu cherez AB_MODE=A.

Zemnoy abzats:
Eto «konveyer»: beret kartu (profil) i skladyvaet nositel po ney bez UI.

# c=a+b
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from modules.selfmanage.usb_profiles import get_profile  # type: ignore
from modules.packaging.release_builder import build_release_archive  # type: ignore
from modules.selfmanage.usb_writer import write_usb  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB Make by Profile")
    ap.add_argument("--profile-id", required=True)
    ap.add_argument("--mount", required=True)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args(argv)

    prof = get_profile(args.profile_id)
    if not prof:
        print(json.dumps({"ok": False, "error": "profile-not-found"}, ensure_ascii=False))
        return 2

    label = prof.get("label") or os.getenv("ESTER_USB_LABEL", "ESTER")
    with_release = bool(prof.get("with_release", True))
    dump_paths = list(prof.get("dump_paths") or [])
    include_dump = dump_paths[0] if dump_paths else None

    archive_path = None
    build_report = None
    if with_release:
        out_dir = Path(".").resolve() if (args.dry or AB != "B") else Path(args.mount).resolve()
        build_report = build_release_archive(output_dir=str(out_dir), include_dump=include_dump)
        if not build_report.get("ok"):
            print(json.dumps({"ok": False, "error": "build-failed", "report": build_report}, ensure_ascii=False, indent=2))
            return 2
        archive_path = build_report.get("archive")

    if args.dry or AB != "B":
        print(json.dumps({"ok": True, "dry": True, "mount": args.mount, "label": label, "archive": archive_path, "dump": include_dump, "build": build_report, "profile": prof}, ensure_ascii=False, indent=2))
        return 0

    rep = write_usb(mount=args.mount, from_archive=archive_path, from_dump=include_dump, label=label)
    print(json.dumps({"ok": bool(rep.get("ok")), "write_report": rep, "build": build_report, "profile": prof}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())