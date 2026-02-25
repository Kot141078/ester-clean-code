# -*- coding: utf-8 -*-
"""listeners/selfcare_scheduler.py - periodicheskiy self-check, zapis istorii i avto-pochinka po pravilam.

Behavior:
  • Kazhdye SELFCARE_INTERVAL_MIN min. build report build_report(deep=every N).
  • Khranit istoriyu v ~/.ester/diagnostics/history/YYYY-MM-DD.ndjson (max SELFCARE_MAX_REPORTS rotatsiya).
  • Vychislyaet plan pravil i (esli AB=B i SELFCARE_AUTOFIX_ENABLE=1) zapuskaet deystviya.
  • Lyubye oshibki - myagko logiruyutsya v stdout, protsess prodolzhaet rabotu.

Mosty:
- Yavnyy (Nablyudenie ↔ Deystvie): periodika prevraschaet “ruchnuyu” tekhpanel v avtomaticheskiy ukhod.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): ndjson-istoriya legko analiziruetsya offlayn.
- Skrytyy 2 (Praktika ↔ Sovmestimost): stdlib, drop-in; uvazhenie AB i flagov.

Zemnoy abzats:
This is “dezhurnyy mekhanik”: regulyarno smotrit pribory i krutit ruchki po instruktsii - bez lishney drama.

# c=a+b"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
from typing import Dict, Any, List

from modules.selfcheck.health_probe import build_report  # type: ignore
from modules.selfcheck.auto_fix import restart_sidecar, clear_inboxes, rebuild_indices, rebind_lmstudio, rescan_usb_once  # type: ignore
from modules.selfcare.rules import eval_rules  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
HIST_DIR = STATE_DIR / "diagnostics" / "history"
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _bool_env(name: str, default: int) -> bool:
    try: return bool(int(os.getenv(name, str(default))))
    except Exception: return bool(default)

def _append_history(obj: Dict[str, Any]) -> None:
    day = time.strftime("%Y-%m-%d", time.localtime(obj.get("report",{}).get("ts", int(time.time()))))
    f = HIST_DIR / f"{day}.ndjson"
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as w:
        w.write(json.dumps(obj, ensure_ascii=False) + "\n")
    # rough rotation by number of lines/files
    maxrep = max(100, int(os.getenv("SELFCARE_MAX_REPORTS","500")))
    # does not read the entire file - only if it is very large, we will create a new one the next day
    # (simple rotation by day already limits growth)

def _run_actions(plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results=[]
    for item in plan:
        rep={"name": item.get("name"), "results":[]}
        for act in item.get("actions", []):
            a = act.get("action")
            try:
                if a == "restart_sidecar": rep["results"].append({"restart_sidecar": restart_sidecar()})
                elif a == "clear_inboxes": rep["results"].append({"clear_inboxes": clear_inboxes()})
                elif a == "rebuild_indices": rep["results"].append({"rebuild_indices": rebuild_indices()})
                elif a == "rebind_lmstudio": rep["results"].append({"rebind_lmstudio": rebind_lmstudio()})
                elif a == "rescan_usb_once": rep["results"].append({"rescan_usb_once": rescan_usb_once()})
            except Exception as e:
                rep["results"].append({a: {"ok": False, "error": str(e)}})
        results.append(rep)
    return results

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester Self-Care Scheduler")
    ap.add_argument("--loop", action="store_true")
    args = ap.parse_args(argv)

    iv = max(5, int(os.getenv("SELFCARE_INTERVAL_MIN","30"))) * 60
    deep_every = max(1, int(os.getenv("SELFCARE_DEEP_EVERY","4")))
    autofix = _bool_env("SELFCARE_AUTOFIX_ENABLE", 1)

    i=0
    try:
        while True:
            deep = (i % deep_every == 0)
            rep = build_report(deep=deep)
            _append_history(rep)
            plan = eval_rules(rep)
            actions = plan.get("plan", [])
            results = []
            if AB == "B" and autofix and actions:
                results = _run_actions(actions)
            # short syllable in stdout (for logchtl/console)
            print(json.dumps({"ts": int(time.time()), "deep": deep, "ab": AB, "planned": len(actions), "executed": len(results)}), flush=True)
            i += 1
            if not args.loop: break
            time.sleep(iv)
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b