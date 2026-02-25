# -*- coding: utf-8 -*-
"""tools/compliance_snapshot.py - CLI: sdelat snapshot i/ili compare dva.

Primery:
  # sokhranit snapshot (AB=A → dry, AB=B → zapis)
  python tools/compliance_snapshot.py --make

  #pokazat spisok
  python tools/compliance_snapshot.py --list

  # sravnit poslednie dva snapshota (USB prioritetno)
  python tools/compliance_snapshot.py --diff

  # compare konkretnye puti
  python tools/compliance_snapshot.py --diff --a /path/to/old.json --b /path/to/new.json

Kody vykhoda:
  0 — uspeshnoe vypolnenie (dazhe pri dry or otsutstvii USB dlya --list/--diff s ukazaniem putey)
  1 - oshibka (for example, net USB i ne zadano putey dlya diff)

Mosty:
- Yavnyy (DevOps ↔ Ekspluatatsiya): te zhe operatsii, chto v UI, dostupny dlya skriptov/CI.
- Skrytyy 1 (Infoteoriya): stabilnyy JSON on stdout.
- Skrytyy 2 (Praktika): stdlib, offflayn; zapis tolko v AB=B.

Zemnoy abzats:
This is “knopka na pulte”: mozhno avtomatizirovat snimok/sravnenie v nochnykh reviziyakh bez UI.

# c=a+b"""
from __future__ import annotations
import argparse, json, sys
from modules.compliance.snapshot import list_snapshots, save_snapshot, load_snapshot, diff_snapshots  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester compliance snapshots")
    ap.add_argument("--make", action="store_true", help="Take a snapshot")
    ap.add_argument("--list", action="store_true", help="Show list of snapshots")
    ap.add_argument("--diff", action="store_true", help="Sravnit dva snapshota")
    ap.add_argument("--a", help="Put k staromu snapshotu", default=None)
    ap.add_argument("--b", help="Put k novomu snapshotu", default=None)
    args = ap.parse_args(argv)

    if args.make:
        res = save_snapshot({})
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1

    if args.list:
        snaps = list_snapshots()
        print(json.dumps(snaps, ensure_ascii=False, indent=2))
        return 0

    if args.diff:
        a_path, b_path = args.a, args.b
        snaps = list_snapshots()
        ordered = snaps.get("usb", []) + snaps.get("local", [])
        if (not a_path or not b_path) and len(ordered) >= 2:
            a_path = a_path or ordered[1]["path"]
            b_path = b_path or ordered[0]["path"]
        if not a_path or not b_path:
            print(json.dumps({"ok": False, "error": "not-enough-snapshots"}, ensure_ascii=False, indent=2))
            return 1
        a = load_snapshot(a_path); b = load_snapshot(b_path)
        rep = diff_snapshots(a, b)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0

    ap.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b