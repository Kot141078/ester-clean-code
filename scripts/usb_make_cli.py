# -*- coding: utf-8 -*-
"""
scripts/usb_make_cli.py — CLI dlya sozdaniya portable-fleshki Ester.

Primery:
  AB_MODE=A python -m scripts.usb_make_cli --mount /media/usb --include-state
  AB_MODE=B python -m scripts.usb_make_cli --mount /media/usb --release ~/build/ester_release.tar.gz --dump ~/data/project/
  python -m scripts.usb_make_cli --mount E:\\ --release C:\\tmp\\rel.zip --compute-sha --dry

Flagi:
  --mount <PATH>           — tochka montirovaniya fleshki (obyazatelen)
  --include-state          — vklyuchit ~/.ester sostoyanie
  --release <FILE>         — arkhiv reliza (optsionalno)
  --dump <FILE|DIR>        — damp (fayl ili papka, optsionalno)
  --label <NAME>           — papka na fleshke (po umolchaniyu ESTER)
  --compute-sha            — schitat SHA256 v manifest (po umolchaniyu vklyucheno)
  --dry                    — prinuditelnyy dry-run (ignoriruet AB_MODE)

Mosty:
- Yavnyy (Kibernetika ↔ Orkestratsiya): sozdaet fleshku bez UI, kak /admin/usb/make.
- Skrytyy 1 (Infoteoriya ↔ Bezopasnost): plan pered deystviem, dry-run dlya proverki.
- Skrytyy 2 (Praktika ↔ Sovmestimost): struktura ESTER/ sovmestima s Zero-Touch agentom.

Zemnoy abzats:
Kak master na vse ruki: sobiraet fleshku s relizami, dampami ili sostoyaniem, ostavlyaet chetkiy plan i otchet. Rabotaet dazhe v starykh sistemakh.

# c=a+b
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Proveryaem dostupnost moduley
try:
    from modules.usb.portable_layout import build_plan, apply_plan  # type: ignore
    HAS_PORTABLE_LAYOUT = True
except ImportError:
    HAS_PORTABLE_LAYOUT = False

try:
    from modules.selfmanage.usb_maker import make_usb  # type: ignore
    HAS_USB_MAKER = True
except ImportError:
    HAS_USB_MAKER = False

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _validate_path(path: str, kind: str) -> tuple[Optional[Path], Optional[str]]:
    """Proveryaet suschestvovanie i prava dostupa k faylu ili papke."""
    if not path:
        return None, None
    p = Path(path)
    if not p.exists():
        return None, f"{kind}-not-found: {path}"
    if not os.access(p, os.R_OK):
        return None, f"{kind}-inaccessible: {path}"
    return p, None

def main(argv: list[str] | None = None) -> int:
    """Osnovnaya logika sozdaniya USB-nositelya."""
    ap = argparse.ArgumentParser(description="Ester USB portable maker")
    ap.add_argument("--mount", required=True, help="tochka montirovaniya fleshki")
    ap.add_argument("--include-state", action="store_true", help="vklyuchit ~/.ester sostoyanie")
    ap.add_argument("--release", default="", help="put k arkhivu reliza (optsionalno)")
    ap.add_argument("--dump", default="", help="put k dampu (fayl/papka, optsionalno)")
    ap.add_argument("--label", default=os.getenv("ESTER_USB_LABEL", "ESTER"), help="papka na fleshke")
    ap.add_argument("--compute-sha", action="store_true", default=True, help="schitat SHA256")
    ap.add_argument("--dry", action="store_true", help="prinuditelnyy dry-run")
    args = ap.parse_args(argv)

    report: Dict = {"ok": True, "module": None, "plan": None, "result": {}, "ab": AB, "dry": args.dry or (AB != "B")}

    # Proveryaem moduli
    if not (HAS_PORTABLE_LAYOUT or HAS_USB_MAKER):
        report = {"ok": False, "error": "no-modules-available", "details": "Neither portable_layout nor usb_maker found"}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    # Proveryaem puti
    release_path, release_error = _validate_path(args.release, "release")
    dump_path, dump_error = _validate_path(args.dump, "dump")
    if release_error or dump_error:
        report = {"ok": False, "error": release_error or dump_error}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    # Proveryaem tochku montirovaniya
    mount_path = Path(args.mount)
    if not mount_path.exists() or not os.access(mount_path, os.W_OK):
        report = {"ok": False, "error": f"mount-inaccessible: {args.mount}"}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    # Vybiraem modul i vypolnyaem
    if HAS_PORTABLE_LAYOUT and (release_path or dump_path or not args.include_state):
        report["module"] = "portable_layout"
        plan = build_plan(
            args.mount,
            release_path,
            dump_path,
            label=args.label,
            compute_sha=bool(args.compute_sha)
        )
        report["plan"] = plan
        report["result"] = apply_plan(plan, dry=(args.dry or AB != "B"))
    elif HAS_USB_MAKER:
        report["module"] = "usb_maker"
        if release_path:
            report = {"ok": False, "error": "release-not-supported", "details": "usb_maker does not support --release"}
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2
        report["result"] = make_usb(args.mount, include_state=args.include_state, dump_path=dump_path)
    else:
        report = {"ok": False, "error": "no-compatible-module", "details": "No module supports the given options"}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"].get("ok") else 2

if __name__ == "__main__":
    raise SystemExit(main())