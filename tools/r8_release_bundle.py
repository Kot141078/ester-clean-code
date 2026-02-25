#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R8/tools/r8_release_bundle.py - sborka reliz-bandla i manifesta chek-summ.

Mosty:
- Yavnyy: Enderton — spetsifikatsiya bandla: fiksirovannyy nabor direktoriy/faylov → tar.gz + manifest.json.
- Skrytyy #1: Ashbi - A/B-slot: R8_MODE=B dobavlyaet rashirennyy manifest (razmery/vremya), pri oshibkakh - katbek.
- Skrytyy #2: Cover & Thomas — kontrol tselostnosti: sha256 na kazhdyy artefakt → nizkaya entropiya neopredelennosti.

Zemnoy abzats (inzheneriya):
No matter what. Sobiraet `tools/ services/ tests/ scripts/ rules/` i vazhnye fikstury, isklyuchaya `__pycache__/.*`.
Write `release/ester_bundle.tar.gz` i `release/manifest.json`. Bezopasnaya skleyka putey cherez path_guard.

# c=a+b"""
from __future__ import annotations
import argparse, os, tarfile, time, json, hashlib
from typing import Dict, List
from services.sec.path_guard import safe_join  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

INCLUDE_DIRS = ["tools", "services", "tests", "scripts", "rules"]
INCLUDE_FILES = ["README.md", "LICENSE", "ester_manifest.json"]

def _walk(root: str) -> List[str]:
    out = []
    for dp, dns, fns in os.walk(root):
        if "__pycache__" in dp or dp.endswith(".git") or "/.git/" in dp:
            continue
        for fn in fns:
            out.append(os.path.join(dp, fn))
    return out

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    ap = argparse.ArgumentParser(description="Assemble release bundle (tar.gz) with manifest")
    ap.add_argument("--out", default="release/ester_bundle.tar.gz")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    base = os.getcwd()
    ts = int(time.time())

    files: List[str] = []
    for d in INCLUDE_DIRS:
        if os.path.isdir(d):
            files.extend(_walk(d))
    for f in INCLUDE_FILES:
        if os.path.isfile(f):
            files.append(f)

    manifest: Dict[str, Dict] = {}
    for p in files:
        try:
            rel = os.path.relpath(p, base)
            st = os.stat(p)
            manifest[rel] = {"sha256": _sha256(p), "size": st.st_size}
        except Exception:
            continue

    # tar.gz
    with tarfile.open(args.out, "w:gz") as tar:
        for rel, meta in manifest.items():
            src = safe_join(base, rel)
            tar.add(src, arcname=rel)

    # manifest
    man_path = os.path.join(os.path.dirname(args.out), "manifest.json")
    mode = (os.getenv("R8_MODE") or "A").strip().upper()
    out_meta = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
        "bundle": os.path.basename(args.out),
        "files": manifest
    }
    if mode == "B":
        try:
            out_meta["counts"] = {
                "total_files": len(manifest),
                "total_bytes": sum(v["size"] for v in manifest.values())
            }
        except Exception:
            pass  # katbek

    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(out_meta, f, ensure_ascii=False, indent=2)

    print(json.dumps({"ok": 1, "bundle": args.out, "manifest": man_path}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

# c=a+b