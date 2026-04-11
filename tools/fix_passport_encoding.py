#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tools/fix_passport_encoding.py

One-time repair for Passport JSONL mojibake (UTF-8 bytes mistakenly decoded as CP1251),
e.g. 'Nu tak ...' -> 'Nu tak ...'

Usage (Windows PowerShell):
  cd <repo-root>
  python .\tools\fix_passport_encoding.py

It will create:
  data\passport\clean_memory.fixed.jsonl
and backup the original:
  data\passport\clean_memory.jsonl.bak_YYYYMMDD_HHMMSS
"""
import os, json, time, shutil, re
from datetime import datetime
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PASSPORT_PATH = os.path.join("data", "passport", "clean_memory.jsonl")

WEIRD_MARKERS = set("ѓїќў‚њЅЈЎ¤€")

def _rs_ratio(s: str) -> float:
    if not s:
        return 0.0
    return (s.count("R") + s.count("S")) / float(len(s))

def looks_mojibake(s: str) -> bool:
    if not s:
        return False
    if any(tok in s for tok in ("\u0432\u0402", "\u0432\u045a", "\u00e2\u20ac")):
        return True
    if "Ð" in s or "Ñ" in s:
        return True
    if any(ch in WEIRD_MARKERS for ch in s) and ("R" in s or "S" in s):
        return True
    if len(s) >= 8 and _rs_ratio(s) > 0.22:
        return True
    return False

def try_fix_cp1251_utf8(s: str) -> str:
    """
    Reverse UTF-8->CP1251 mojibake:
      correct_utf8_bytes decoded as cp1251 -> garbage Cyrillic
    Fix by encoding back to cp1251 bytes and decoding as utf-8.
    """
    if not s or not isinstance(s, str):
        return s
    if not looks_mojibake(s):
        return s

    # strict first, then tolerant
    for enc_errors in ("strict", "ignore"):
        for dec_errors in ("strict", "ignore"):
            try:
                fixed = s.encode("cp1251", errors=enc_errors).decode("utf-8", errors=dec_errors)
            except Exception:
                continue
            if not fixed:
                continue

            # accept only if it really improves
            # heuristic: fixed should reduce RS-density and keep Cyrillic letters readable
            if _rs_ratio(fixed) + 0.05 < _rs_ratio(s):
                return fixed
    return s

def fix_any(x):
    if isinstance(x, str):
        return try_fix_cp1251_utf8(x)
    if isinstance(x, list):
        return [fix_any(v) for v in x]
    if isinstance(x, dict):
        return {k: fix_any(v) for k, v in x.items()}
    return x

def main():
    if not os.path.exists(PASSPORT_PATH):
        print(f"[ERR] Not found: {PASSPORT_PATH}")
        return 1

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = PASSPORT_PATH + f".bak_{ts}"
    fixed_path = os.path.join("data", "passport", "clean_memory.fixed.jsonl")

    os.makedirs(os.path.dirname(PASSPORT_PATH), exist_ok=True)

    # backup original
    shutil.copy2(PASSPORT_PATH, backup_path)
    print(f"[OK] Backup: {backup_path}")

    total = 0
    changed = 0

    with open(PASSPORT_PATH, "r", encoding="utf-8", errors="replace") as f_in, \
         open(fixed_path, "w", encoding="utf-8") as f_out:
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                obj = json.loads(line)
            except Exception:
                # keep raw line if it is broken JSON
                f_out.write(line + "\n")
                continue

            before = json.dumps(obj, ensure_ascii=False)
            obj2 = fix_any(obj)
            after = json.dumps(obj2, ensure_ascii=False)

            if after != before:
                changed += 1

            f_out.write(after + "\n")

    print(f"[OK] Written: {fixed_path}")
    print(f"[OK] Lines: {total}, changed: {changed}")
    print("\nNext step (manual, after checking):")
    print("  1) Open data\\passport\\clean_memory.fixed.jsonl and verify Russian text looks normal")
    print("  2) Replace the original:")
    print("     Move-Item .\\data\\passport\\clean_memory.jsonl .\\data\\passport\\clean_memory.corrupt.jsonl -Force")
    print("     Move-Item .\\data\\passport\\clean_memory.fixed.jsonl .\\data\\passport\\clean_memory.jsonl -Force")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
