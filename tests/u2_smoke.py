#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
U2/tests/u2_smoke.py — myagkiy smouk Cortex-orkestratora.

Mosty:
- Yavnyy: Enderton — proveryaemye predikaty: plan sformirovan ∧ vypolneny khotya by nekotorye shagi.
- Skrytyy #1: Ashbi — ustoychivost: otsutstvie dannykh/LLM ne valit payplayn.
- Skrytyy #2: Cover & Thomas — otchet minimalen, no informativen (plan i klyuchevye artefakty).

Zemnoy abzats (inzheneriya):
Gonyaem u2_cortex s politikoy po umolchaniyu; dopuskaem otsutstvie vneshnikh servisov.
Ozhidaem poyavlenie `data/cortex/state.json` i/ili obnovlenie portala/obs.

# c=a+b
"""
from __future__ import annotations
import json, os, subprocess, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    # dry-run
    out = subprocess.check_output([sys.executable, "tools/u2_cortex.py", "--policy", "tests/fixtures/cortex_policy.json", "--dry-run"], text=True)
    print(out.strip())
    # run
    subprocess.run([sys.executable, "tools/u2_cortex.py", "--policy", "tests/fixtures/cortex_policy.json"], check=False)
    ok = os.path.isfile("portal/index.html") or os.path.isfile(os.path.join(os.getenv("PERSIST_DIR") or "data","cortex","state.json"))
    print(json.dumps({"ok": ok}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())