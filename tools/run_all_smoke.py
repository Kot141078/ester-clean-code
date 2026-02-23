#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/run_all_smoke.py — svodnyy myagkiy progon smoukov R2–R8, U1, U2.

Mosty:
- Yavnyy: Enderton — fiksirovannaya posledovatelnost komand, kazhdaya s nablyudaemym rezultatom.
- Skrytyy #1: Ashbi — myagkiy rezhim: oshibki ne valyat ranner; fiksiruem RC i dvizhemsya dalshe.
- Skrytyy #2: Cover & Thomas — na vykhod — kompaktnyy JSON-itog, dostatochnyy dlya priemki.

Zemnoy abzats:
Vypolnyaet smouki po ocheredi: ingenst → indeks → rerank (fallback dopustim) → daydzhest → pravila → render →
nablyudaemost → bezopasnost/reliz → sovetnik → Cortex (dry-run + run). Podkhodit dlya lokalnoy «revizii».

# c=a+b
"""
from __future__ import annotations
import json, subprocess, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

CMDS = [
    [sys.executable, "tests/r2_trigger_smoke.py"],
    [sys.executable, "tests/r3_smoke.py"],
    [sys.executable, "tests/r4_smoke.py"],
    [sys.executable, "tests/r5_smoke.py"],
    [sys.executable, "tests/r6_smoke.py"],
    [sys.executable, "tests/r7_smoke.py"],
    [sys.executable, "tests/r8_smoke.py"],
    [sys.executable, "tests/u1_smoke.py"],
    [sys.executable, "tools/u2_cortex.py", "--policy", "tests/fixtures/cortex_policy.json", "--dry-run"],
    [sys.executable, "tests/u2_smoke.py"],
]

def main() -> int:
    results = []
    for cmd in CMDS:
        try:
            rc = subprocess.run(cmd, check=False).returncode
        except Exception:
            rc = -1
        results.append({"cmd": " ".join(str(x) for x in cmd), "rc": rc})
    ok = all(r["rc"] == 0 for r in results if "u2_cortex.py --dry-run" in r["cmd"] or "tests/u2_smoke.py" in r["cmd"])
    print(json.dumps({"ok": ok, "steps": results}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())