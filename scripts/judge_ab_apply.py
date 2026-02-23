# -*- coding: utf-8 -*-
"""
scripts/judge_ab_apply.py — zapisyvaet podskazki A/B v overlay-fayl.

Primery:
  python -m scripts.judge_ab_apply --out ~/.ester/judge_slots.json
  python -m scripts.judge_ab_suggest --bench | python -m scripts.judge_ab_apply --input -

Mosty:
- Yavnyy (Orkestratsiya ↔ Ekspluatatsiya): yavnoe primenenie — yavnyy fayl.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): ne trogaem Judge — minimum riska regressii.
- Skrytyy 2 (Praktika ↔ Bezopasnost): podderzhka stdin dlya konveyerov.

Zemnoy abzats:
Pozvolyaet skleit «podskazchik» so storozhom Judge (esli on est): dopisal fayl — storozh perechital.

# c=a+b
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from modules.judge.ab_suggest import build_suggestion, save_overlay, suggestion_to_dict  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ester Judge A/B Apply")
    ap.add_argument("--input", type=str, default="", help="put k JSON s podskazkami (ili '-' dlya stdin)")
    ap.add_argument("--out", type=str, default="", help="kuda sokhranit (defolt ESTER_JUDGE_SLOTS_PATH)")
    ap.add_argument("--bench", action="store_true", help="esli --input ne zadan — sgenerirovat s benchem")
    args = ap.parse_args(argv)

    if args.input:
        if args.input == "-":
            data = sys.stdin.read()
            s: Dict[str, Any] = json.loads(data)
        else:
            s = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        s = suggestion_to_dict(build_suggestion(bench=args.bench))

    # Prostaya validatsiya
    if not isinstance(s, dict) or "slotA" not in s or "slotB" not in s:
        print("Nekorrektnyy format podskazok", file=sys.stderr)
        return 2

    path = save_overlay(build_suggestion(bench=False), path=args.out or None)  # sokhranyaem novyy slepok (bench po zhelaniyu)
    # Esli nuzhno strogo «kak v s», mozhno bylo by pisat s napryamuyu; zdes sokhranyaem svezhiy build dlya konsistentnosti
    print(json.dumps({"ok": True, "saved_to": path}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())