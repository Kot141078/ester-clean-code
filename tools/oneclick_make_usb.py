# -*- coding: utf-8 -*-
"""tools/oneclick_make_usb.py - CLI: sobrat perenosimuyu fleshku ESTER (One-Click).

Use:
  #predprosmotr
  python tools/oneclick_make_usb.py --preview

  # zapisat (AB=A → dry, AB=B → zapis)
  AB_MODE=B python tools/oneclick_make_usb.py --apply

Vykhodnye kody:
  0 - uspekh (vklyuchaya dry)
  1 — oshibka (net USB/isklyucheniya)

Mosty:
- Yavnyy (DevOps ↔ UX): to zhe, chto v UI, dostupno dlya avtomatizatsii.
- Skrytyy 1 (Infoteoriya): baseline vklyuchaetsya v sborku srazu.
- Skrytyy 2 (Praktika): offflayn/stdlib; zapis pod AB=B.

Zemnoy abzats:
CLI-dubler knopki: udobno dlya skriptov i “tikhikh” sborok bez UI.

# c=a+b"""
from __future__ import annotations
import argparse, json, sys
from modules.portable.oneclick import preview, build_plan, apply_plan  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester One-Click USB")
    ap.add_argument("--preview", action="store_true", help="Predprosmotr plana")
    ap.add_argument("--apply", action="store_true", help="Primenit plan")
    args = ap.parse_args(argv)

    if args.preview:
        print(json.dumps(preview(), ensure_ascii=False, indent=2))
        return 0
    if args.apply:
        plan = build_plan()
        res = apply_plan(plan)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1

    ap.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b