# -*- coding: utf-8 -*-
"""
tools/generate_baseline.py — CLI: pechat baseline.json v stdout.

Zapusk:
  python tools/generate_baseline.py > baseline.json

Vozvraschaet kod 0 vsegda (dazhe esli chast faylov nedostupna): baseline — vspomogatelnyy slepok, ne «stop-kran».

Mosty:
- Yavnyy (DevOps ↔ Sborka): bystryy artefakt baseline dlya posleduyuschikh sravneniy v CI/oflayne.
- Skrytyy 1 (Infoteoriya): mashinno-chitaemyy i vosproizvodimyy JSON.
- Skrytyy 2 (Praktika): chistyy stdlib; yadro Ester ne zatragivaetsya.

Zemnoy abzats:
Eto «knopka fotoapparata»: snyal tekuschee polozhenie rychagov — i pones fayl v drugoy tsekh dlya sverki.

# c=a+b
"""
from __future__ import annotations
import json, sys
from modules.compat.baseline_builder import build_baseline  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv=None) -> int:
    obj = build_baseline()
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.stdout.flush()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b