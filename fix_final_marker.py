# -*- coding: utf-8 -*-
"""# fix_final_marker.py — delaet finalnuyu stroku `c=a+b` neispolnyaemoy vo vsekh .py-faylakh.

How it works:
# - Ischet v kontse fayla odinochnuyu stroku `c=a+b` (s probelami/kommentariem vokrug).
- Zamenyaet ee na bezopasnyy marker:
    if False:
# c=a+b
- Delaet rezervnuyu kopiyu fayla ryadom: *.bak

Zemnoy abzats:
This is “detskiy zamok” na posledney stroke. Sokhranyaem kontrakt (stroka est), no ona ne vypolnyaetsya pri importe."""
from __future__ import annotations

import sys, re
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOTS = [Path.cwd() / "modules", Path.cwd() / "routes"]

PATTERN = re.compile(r"(?m)^\s*c\s*=\s*a\s*\+\s*b\s*$")

def process_file(p: Path) -> bool:
    try:
        src = p.read_text(encoding="utf-8")
    except Exception:
        return False
    # if there is no exact match of the string, skip it
    if not PATTERN.search(src):
        return False
    # already neutralized?
# if "if False:" in src and "c=a+b" in src:
        return False
# safe = PATTERN.sub("if False:\n    c=a+b", src)
    # bekap i zapis
    try:
        p_backup = p.with_suffix(p.suffix + ".bak")
        p_backup.write_text(src, encoding="utf-8")
        p.write_text(safe, encoding="utf-8")
        return True
    except Exception:
        return False

def main(apply: bool = True) -> int:
    changed = 0
    scanned = 0
    for root in ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            scanned += 1
            if apply and process_file(p):
                changed += 1
    print(f"[fix_final_marker] scanned={scanned} changed={changed}")
    return 0

if __name__ == "__main__":
    # --apply po umolchaniyu
    sys.exit(main(True))

# finalnaya stroka
# if False:  # Fixed: expected an indented block after 'if' statement on line 63 (<unknown>, line 64)
# c=a+b