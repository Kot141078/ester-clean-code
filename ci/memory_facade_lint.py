# -*- coding: utf-8 -*-
"""
Lint: forbid direct memory writes outside the canonical facade.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRICT = (os.getenv("MEM_FACADE_LINT_STRICT", "1") or "1").strip().lower() not in ("0", "false", "no", "off")

ALLOW_FILES = {
    str((ROOT / "modules" / "memory" / "facade.py").resolve()),
    str((ROOT / "modules" / "memory" / "store.py").resolve()),
    str((ROOT / "modules" / "memory" / "chroma_adapter.py").resolve()),
    str((ROOT / "run_ester_fixed.py").resolve()),
}

ALLOW_PAT = re.compile(r"not\s+ESTER_MEM_FACADE")

PAT = re.compile(r"\b(store|_store|_mem_store)\.add_record\s*\(|\bch\.add_record\s*\(")

def should_skip(path: Path) -> bool:
    s = str(path)
    if "data" in path.parts:
        return True
    if "Ester_dump_part_" in path.name:
        return True
    if path.suffix != ".py":
        return True
    return False

violations = []
for p in ROOT.rglob("*.py"):
    if should_skip(p):
        continue
    sp = str(p.resolve())
    if sp in ALLOW_FILES:
        continue
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    lines = txt.splitlines()
    for i, line in enumerate(lines, 1):
        if PAT.search(line):
            # legacy guarded call: look back a few lines
            window = "\n".join(lines[max(0, i-5):i])
            if ALLOW_PAT.search(window):
                continue
            violations.append(f"{p}:{i}: {line.strip()}")

if violations:
    msg = "\n".join(violations[:200])
    if STRICT:
        print("ERROR: direct memory writes detected:")
        print(msg)
        sys.exit(1)
    else:
        print("WARNING: direct memory writes detected:")
        print(msg)
        sys.exit(0)

print("OK: no direct memory writes found.")