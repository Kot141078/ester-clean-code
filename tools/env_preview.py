# -*- coding: utf-8 -*-
"""
tools/env_preview.py — CLI: import recommend.env, predprosmotr diff i zapis active.env.

Primery:
  # Predprosmotr diff (ispolzuya recommend.env s USB)
  python tools/env_preview.py --preview

  # Predprosmotr diff dlya proizvolnogo fayla
  python tools/env_preview.py --preview --file /path/to/file.env

  # Zapisat active.env na USB (AB=A → dry, AB=B → zapis)
  python tools/env_preview.py --apply
  python tools/env_preview.py --apply --file /path/to/file.env

Kody vykhoda:
  0 — uspekh (vklyuchaya dry)
  1 — oshibka (net USB/net fayla)

Mosty:
- Yavnyy (DevOps ↔ UX): te zhe operatsii dostupny bez UI.
- Skrytyy 1 (Infoteoriya): edinyy parser/diff.
- Skrytyy 2 (Praktika): zapis tolko v portable/*; offlayn, stdlib, AB-guard.

Zemnoy abzats:
Eto «knopka bez brauzera»: bystro ponyat otlichiya i polozhit aktivnyy ENV na fleshku.

# c=a+b
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from modules.env.panel import load_recommend_env, parse_env_text, current_env, diff_env, write_active_env  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester ENV preview/apply")
    ap.add_argument("--preview", action="store_true", help="Predprosmotr diff")
    ap.add_argument("--apply", action="store_true", help="Zapisat active.env na USB")
    ap.add_argument("--file", help="Put k istochniku .env (esli ne ukazan — berem recommend.env s USB)", default=None)
    args = ap.parse_args(argv)

    text = ""
    if args.file:
        p = Path(args.file)
        if not p.exists():
            print(json.dumps({"ok": False, "error": "file-not-found", "path": str(p)}, ensure_ascii=False, indent=2))
            return 1
        text = _read_text(p)
    else:
        rec = load_recommend_env()
        if not rec.get("ok") or not rec.get("text"):
            print(json.dumps({"ok": False, "error": rec.get("error","recommend-not-found")}, ensure_ascii=False, indent=2))
            return 1
        text = rec["text"]  # type: ignore

    vars_file = parse_env_text(text)
    cur = current_env(list(vars_file.keys()))
    d = diff_env(vars_file, cur)

    if args.preview and not args.apply:
        print(json.dumps({"ok": True, "diff": d, "vars_count": len(vars_file)}, ensure_ascii=False, indent=2))
        return 0

    if args.apply:
        res = write_active_env(vars_file)
        out = {"ok": bool(res.get("ok")), "result": res, "diff": d}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1

    ap.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b