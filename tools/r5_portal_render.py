#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R5/tools/r5_portal_render.py - CLI: staticheskiy offlayn-render portala (HTML) iz poslednego daydzhesta.

Mosty:
- Yavnyy: Enderton - JSON → HTML po fiksirovannomu shablonu (determinirovannyy mapping).
- Skrytyy #1: Cover & Thomas — akkuratno vizualiziruem poleznyy “signal” (summary/tegi).
- Skrytyy #2: Ashbi — A/B-rezhim na urovne stiley/lentochek ne lomaet vyvod (katbek).

Zemnoy abzats:
Ischet posledniy fayl v `PERSIST_DIR/portal/digests/`, konvertiruet v `--out` (napr. `portal/index.html`).
Nikakikh zavisimostey, result otkryvaetsya file:// lokalno.

# c=a+b"""
from __future__ import annotations
import argparse
import glob
import json
import os
from services.portal.template import render_html  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _latest_digest_path(portal_dir: str) -> str | None:
    paths = sorted(glob.glob(os.path.join(portal_dir, "digests", "digest_*.json")))
    return paths[-1] if paths else None

def main() -> int:
    ap = argparse.ArgumentParser(description="Render of a static portal page from the latest digest")
    ap.add_argument("--out", required=True, help="Path to output HTML (for example, portal/index.html)")
    args = ap.parse_args()

    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    portal_dir = os.path.join(base, "portal")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    p_json = _latest_digest_path(portal_dir)
    if not p_json:
        print("VARN: no digests. First build: p5_digest_build.by --plan...")
        return 0

    digest = json.load(open(p_json, "r", encoding="utf-8"))
    html = render_html(digest)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[R5] portal written: {args.out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())