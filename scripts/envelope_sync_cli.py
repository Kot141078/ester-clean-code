# -*- coding: utf-8 -*-
"""
scripts/envelope_sync_cli.py — CLI dlya sinkhronizatsii po konvertu (fayl ili JSON-stroka).

Primery:
  AB_MODE=A python -m scripts.envelope_sync_cli --file ~/.ester/inbox/projects/envelopes/1699999999_proj.json
  AB_MODE=B python -m scripts.envelope_sync_cli --json "$(cat .../env.json)"
  AB_MODE=B python -m scripts.envelope_sync_cli --file env.json --profile-id my-profile

Optsii:
  --file        — put k JSON-faylu konverta
  --json        — stroka JSON konverta
  --dry         — prinuditelnyy dry-run (ignoriruet AB_MODE)
  --profile-id  — profil sinkhronizatsii (optsionalno)

Mosty:
- Yavnyy (Kibernetika ↔ Orkestratsiya): odna komanda primenyaet konvert po skheme ili profilyu.
- Skrytyy 1 (Infoteoriya ↔ Bezopasnost): proverka podpisi i JSON-otchet, kak v UI.
- Skrytyy 2 (Praktika ↔ Ekspluatatsiya): obratnaya sovmestimost, novye flagi optsionalny.

Zemnoy abzats:
Kak kurer s posylkoy: beret konvert, proveryaet podpis, akkuratno dostavlyaet po adresu (s profilem ili bez). Udobno dlya avtomatizatsiy i payplaynov.

# c=a+b
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Optional

from modules.selfmanage.envelope_sync import apply_envelope  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Proveryaem nalichie apply_envelope_with_profile
try:
    from modules.selfmanage.envelope_sync import apply_envelope_with_profile  # type: ignore
    HAS_PROFILE_SUPPORT = True
except ImportError:
    HAS_PROFILE_SUPPORT = False

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _load_envelope(args: argparse.Namespace) -> tuple[Optional[Dict], Optional[str]]:
    """Zagruzhaet konvert iz fayla ili stroki JSON."""
    if args.file:
        file_path = Path(args.file)
        try:
            if not file_path.exists():
                return None, f"file-not-found: {args.file}"
            if not file_path.is_file() or not os.access(file_path, os.R_OK):
                return None, f"file-inaccessible: {args.file}"
            return json.loads(file_path.read_text(encoding="utf-8")), None
        except json.JSONDecodeError:
            return None, f"invalid-json: {args.file}"
    else:
        try:
            return json.loads(args.json), None
        except json.JSONDecodeError:
            return None, f"invalid-json: {args.json}"

def main(argv: list[str] | None = None) -> int:
    """Osnovnaya logika sinkhronizatsii po konvertu."""
    ap = argparse.ArgumentParser(description="Ester envelope sync CLI")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", type=str, help="put k JSON-faylu konverta")
    src.add_argument("--json", type=str, help="stroka JSON konverta")
    ap.add_argument("--profile-id", type=str, default="", help="profil sinkhronizatsii (optsionalno)")
    ap.add_argument("--dry", action="store_true", help="prinuditelnyy dry-run")
    args = ap.parse_args(argv)

    # Zagruzhaem konvert
    env, error = _load_envelope(args)
    if error:
        print(json.dumps({"ok": False, "error": error}, ensure_ascii=False, indent=2))
        return 2

    # Opredelyaem rezhim dry-run
    dry = args.dry or (AB != "B")

    # Primenyaem konvert
    report: Dict = {"ok": True, "dry": dry, "profile_id": args.profile_id or None}
    try:
        if args.profile_id:
            if not HAS_PROFILE_SUPPORT:
                report = {"ok": False, "error": "profile-support-unavailable"}
            else:
                report = apply_envelope_with_profile(env, args.profile_id, dry=dry)
        else:
            report = apply_envelope(env, dry=dry)
    except Exception as e:
        report = {"ok": False, "error": f"sync-failed: {str(e)}"}

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2

if __name__ == "__main__":
    raise SystemExit(main())