#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
U2/tools/u2_cortex.py — «Ester sama zapuskaet»: orkestrator, kotoryy dumaet (proactive) i ispolnyaet plan.

Mosty:
- Yavnyy: Enderton — posledovatelnost determinirovannykh shagov (ingest→index→digest→rules→render→advice→slo→release).
- Skrytyy #1: Ashbi — A/B-slot (B mozhet pereuporyadochit cherez lokalnyy LLM); pri sboe — avto-otkat v A.
- Skrytyy #2: Cover & Thomas — minimalnyy otchet/metriki: zapisyvaem tolko fakt zapuska, vremya i RC.

Zemnoy abzats (inzheneriya):
Nikakikh demonov i seti. Fayl politiki zadaet porogi/vklyuchalki. Ispolnenie — cherez suschestvuyuschie CLI,
s metrikami (R7). Sostoyanie tem sokhranyaetsya v `data/cortex/state.json`. Podkhodit dlya cron: «kazhdyy chas/den».

# c=a+b
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from typing import List

from services.brain.proactive import think_and_plan, commit_state  # type: ignore
from services.obs.metrics import record  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _run(cmd: List[str]) -> int:
    try:
        rc = subprocess.run(cmd, check=False).returncode
    except Exception:
        rc = -1
    # metrika odnogo shaga
    record("cmd", {"rc": rc, "ms": 0.0, "cmd": cmd, "tag": "u2"})
    return rc

def main() -> int:
    ap = argparse.ArgumentParser(description="Ester Cortex Orchestrator")
    ap.add_argument("--policy", default="", help="JSON s porogami i flagami (sm. tests/fixtures/cortex_policy.json)")
    ap.add_argument("--ingest-config", default=os.getenv("U1_INGEST_CONFIG") or "tests/fixtures/ingest_config.json")
    ap.add_argument("--rules", default=os.getenv("U1_RULES") or "tests/fixtures/rules_config.json")
    ap.add_argument("--dry-run", action="store_true", help="Tolko pokazat plan, bez ispolneniya")
    args = ap.parse_args()

    plan = think_and_plan(args.policy if args.policy else None)
    print(json.dumps({"plan": plan}, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0

    for a in plan["actions"]:
        if a == "ingest":
            _run([sys.executable, "tools/r2_trigger.py", "--config", args.ingest_config])
        elif a == "index":
            _run([sys.executable, "tools/r3_index_build.py"])
        elif a == "digest":
            # stroim plan iz tem (U1 vnutri)
            _run([sys.executable, "tools/u1_advisor.py", "--top", "6", "--rules", args.rules, "--ingest-config", args.ingest_config])
        elif a == "rules":
            if os.path.isfile(args.rules):
                _run([sys.executable, "tools/r6_apply_rules.py", "--rules", args.rules])
        elif a == "render":
            _run([sys.executable, "tools/r5_portal_render.py", "--out", "portal/index.html"])
        elif a == "advice":
            # sovet uzhe gotovitsya U1, no na vsyakiy sluchay obnovim (bez konteksta chitaet pamyat)
            _run([sys.executable, "tools/u1_advisor.py", "--top", "6", "--rules", args.rules, "--ingest-config", args.ingest_config])
        elif a == "slo":
            _run([sys.executable, "tools/r7_slo_report.py", "--config", "tests/fixtures/slo_config.json", "--out", "obs_report.md"])
        elif a == "release":
            _run([sys.executable, "tools/r8_release_bundle.py", "--out", "release/ester_bundle.tar.gz"])
        else:
            # neizvestnoe — propusk
            pass

    # Fiksiruem otpechatok tem (dlya sleduyuschego shaga proact)
    if plan.get("topics_fp"):
        commit_state(plan["topics_fp"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

# c=a+b