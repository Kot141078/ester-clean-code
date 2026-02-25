#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R6/tools/r6_apply_rules.py - CLI: primenit pravila k poslednemu daydzhestu i zapisat R6-versiyu.

Mosty:
- Yavnyy: Enderton — konfig pravil kak proveryaemaya spetsifikatsiya; resultat determinirovanno vosproizvodim.
- Skrytyy #1: Cover & Thomas — umenshaem izbytochnost i povyshaem raznoobrazie (MMR) → luchshiy “signal”.
- Skrytyy #2: Ashbi — A/B-slot cherez ENV R6_MODE s bezopasnym katbekom v A.

Zemnoy abzats (inzheneriya):
Nakhodit posledniy `digest_*.json` v `PERSIST_DIR/portal/digests/`, primenyaet pravila i pishet
novye fayly `digest_..._r6.json` i `digest_..._r6.md`. Only stdlib.

# c=a+b"""
from __future__ import annotations
import argparse
import glob
import json
import os
from typing import Dict, Tuple

from services.portal.rules import apply_rules_to_digest  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _paths():
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    digdir = os.path.join(base, "portal", "digests")
    os.makedirs(digdir, exist_ok=True)
    return digdir

def _latest_digest(digdir: str) -> str | None:
    paths = sorted(glob.glob(os.path.join(digdir, "digest_*.json")))
    return paths[-1] if paths else None

def _write_md(digest: Dict, path_md: str) -> None:
    lines = []
    lines.append(f"# {digest.get('title','Ester Digest (R6)')}\n")
    lines.append(f"_UTC: {digest.get('generated_utc','')}, mode={digest.get('mode','A')} (R6)_\n")
    for s in digest.get("sections", []):
        lines.append(f"## {s.get('query')}  {' '.join('`#'+t for t in (s.get('tags') or []))}")
        for i, it in enumerate(s.get("items", []), 1):
            lines.append(f"{i}. {it.get('summary')}  — _tags: {', '.join(it.get('tags') or [])}_")
        lines.append("")
    with open(path_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def main() -> int:
    ap = argparse.ArgumentParser(description="Application of the rules of the Republic of Belarus to the latest digest")
    ap.add_argument("--rules", required=True, help="Put k JSON s pravilami")
    args = ap.parse_args()

    digdir = _paths()
    p_in = _latest_digest(digdir)
    if not p_in:
        print("VARN: there are no ready-made digests. First - p5_digest_build.by --plan...")
        return 0

    digest = json.load(open(p_in, "r", encoding="utf-8"))
    rules = json.load(open(args.rules, "r", encoding="utf-8"))

    new, stats = apply_rules_to_digest(digest, rules)

    base, ext = os.path.splitext(p_in)
    p_json = f"{base}_r6.json"
    p_md = f"{base}_r6.md"

    with open(p_json, "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=2)
    _write_md(new, p_md)

    print(json.dumps({"ok": 1, "in": p_in, "out_json": p_json, "out_md": p_md, "stats": stats}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())