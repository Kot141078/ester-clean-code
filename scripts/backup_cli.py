# -*- coding: utf-8 -*-
"""scripts/backup_cli.py - CLI dlya eksporta/importa bandla i sborki fleshki-repliki.

Primery:
  # Eksport v fayl
  python -m scripts.backup_cli --export /tmp/ester_bundle.json

  # Import iz fayla (merge | overwrite), AB_MODE=B - primenit
  AB_MODE=B python -m scripts.backup_cli --import /tmp/ester_bundle.json --mode merge

  # Sozdat fleshku-repliku na /media/USB (v AB_MODE=B - realno zapishet)
  AB_MODE=B python -m scripts.backup_cli --clone /media/USB --label ESTER

Flagi (vzaimoisklyuchayuschie):
  --export <path>
  --import <path> [--mode merge|overwrite]
  --clone <mount> [--label <name>]

Mosty:
- Yavnyy (Ekspluatatsiya ↔ Orkestratsiya): to zhe, chto UI, no iz konsoli i skriptov.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): pechat otcheta/plana.
- Skrytyy 2 (Praktika ↔ Bezopasnost): uvazhaet A/B-sloty.

Zemnoy abzats:
Mozhno snyat/nalozhit nastroyki i sobrat repliku bez brauzera — udobno dlya avtomatizatsii.

# c=a+b"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from modules.selfmanage.backup_settings import export_bundle, import_bundle  # type: ignore
from modules.usb.usb_replicator import create_replica  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester backup/export/clone CLI")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--export", dest="export_path")
    g.add_argument("--import", dest="import_path")
    g.add_argument("--clone", dest="clone_mount")
    ap.add_argument("--mode", choices=["merge","overwrite"], default="merge")
    ap.add_argument("--label", default=None)
    args = ap.parse_args(argv)

    if args.export_path:
        b = export_bundle()
        Path(args.export_path).write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, "written": args.export_path, "bytes": len(json.dumps(b))}, ensure_ascii=False, indent=2))
        return 0

    if args.import_path:
        j = json.loads(Path(args.import_path).read_text(encoding="utf-8"))
        rep = import_bundle(j, mode=args.mode, dry=(AB != "B"))
        print(json.dumps({"ok": rep.get("ok", False), "ab": AB, "result": rep}, ensure_ascii=False, indent=2))
        return 0 if rep.get("ok") else 2

    if args.clone_mount:
        b = export_bundle()
        rep = create_replica(args.clone_mount, bundle=b, label=args.label, dry=(AB != "B"))
        print(json.dumps({"ok": rep.get("ok", False), "ab": AB, "result": rep}, ensure_ascii=False, indent=2))
        return 0 if rep.get("ok") else 2

    return 1

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b