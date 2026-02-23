
# -*- coding: utf-8 -*-
"""
tools.verify_repo — obzornaya proverka proekta.
Mosty:
- Yavnyy: validiruem nalichie/import klyuchevykh paketov i simvolov.
- Skrytyy #1: (DX ↔ Nablyudaemost) — pechataem agregirovannoe sostoyanie mostov.
- Skrytyy #2: (Inzheneriya ↔ Bezopasnost) — nichego ne pishet/ne menyaet v repo.

Zemnoy abzats:
Pered integratsiey udobno bystro proverit «kosti i sukhozhiliya» proekta: importy, mosty, bazovye simvoly. Eto delaet skript.
# c=a+b
"""
import os, sys, re
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _ok(name, fn):
    try:
        val = fn()
        print(f"[OK] {name}: {val!r}")
    except Exception as e:
        print(f"[ERR] {name}: {e}")

def scan_imports():
    pats = re.compile(r'^(?:from\s+([a-zA-Z0-9_.]+)\s+import|import\s+([a-zA-Z0-9_.]+))', re.M)
    total = 0
    mod_hits = {}
    for p in ROOT.rglob("*.py"):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in pats.finditer(txt):
            total += 1
            mod = m.group(1) or m.group(2)
            mod = mod.strip()
            mod_hits[mod] = mod_hits.get(mod, 0) + 1
    print(f"[INFO] scanned imports: {total}, unique modules: {len(mod_hits)}")
    for k in sorted([m for m in mod_hits if m.startswith(("modules.", "memory", "quality", "listeners", "messaging"))]):
        print(f"  - {k}: {mod_hits[k]}")

def main():
    print(f"[INFO] project root: {ROOT}")
    # 1) Bazovye mosty
    _ok("modules.listeners", lambda: __import__("modules.listeners"))
    _ok("modules.messaging", lambda: __import__("modules.messaging"))
    _ok("modules.quality.guard.enable", lambda: __import__("modules.quality.guard", fromlist=["enable"]).enable())
    _ok("memory.decay_gc.run", lambda: hasattr(__import__("memory.decay_gc", fromlist=["run"]), "run"))
    _ok("modules.act.runner.run_plan", lambda: hasattr(__import__("modules.act.runner", fromlist=["run_plan"]), "run_plan"))
    _ok("modules.thinking.loop_full.status", lambda: hasattr(__import__("modules.thinking.loop_full", fromlist=["status"]), "status"))
    print("[INFO] scanning imports…")
    scan_imports()
    print("done.")

if __name__ == "__main__":
    main()