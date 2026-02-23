# -*- coding: utf-8 -*-
"""
scripts/autostart_install.py — CLI upravlenie avtozapuskom USB-agenta.

Primery:
  AB_MODE=A python -m scripts.autostart_install --status
  AB_MODE=B python -m scripts.autostart_install --install
  AB_MODE=B python -m scripts.autostart_install --uninstall

Flagi:
  --status
  --install
  --uninstall

Mosty:
- Yavnyy (Kibernetika ↔ Orkestratsiya): zerkalit vozmozhnosti UI iz CLI.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): vyvodit plan artefaktov.
- Skrytyy 2 (Praktika ↔ Bezopasnost): uvazhaet A/B — sukhoy progon/zapis.

Zemnoy abzats:
Dlya avtomatizatsiy i obrazov — vklyuchit/vyklyuchit avtozapusk komandoy.

# c=a+b
"""
from __future__ import annotations

import argparse
import json
import os

from modules.selfmanage.autostart_manager import plan_install, apply_install, plan_uninstall, apply_uninstall, status  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB Agent Autostart")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--status", action="store_true")
    g.add_argument("--install", action="store_true")
    g.add_argument("--uninstall", action="store_true")
    args = ap.parse_args(argv)

    if args.status:
        print(json.dumps({"ok": True, "ab": AB, "status": status()}, ensure_ascii=False, indent=2))
        return 0

    if args.install:
        plan = plan_install()
        rep = apply_install(plan, dry=(AB != "B"))
        print(json.dumps({"ok": rep.get("ok", False), "ab": AB, "plan": {"os": plan.get("os"), "artifacts": [{"path": str(a.path), "kind": a.kind} for a in plan.get("artifacts", [])], "commands": plan.get("commands")}, "result": rep}, ensure_ascii=False, indent=2))
        return 0 if rep.get("ok") else 2

    if args.uninstall:
        plan = plan_uninstall()
        rep = apply_uninstall(plan, dry=(AB != "B"))
        print(json.dumps({"ok": rep.get("ok", False), "ab": AB, "plan": {"os": plan.get("os"), "artifacts": [{"path": str(a.path), "kind": a.kind} for a in plan.get("artifacts", [])], "commands": plan.get("commands")}, "result": rep}, ensure_ascii=False, indent=2))
        return 0 if rep.get("ok") else 2

    return 1

if __name__ == "__main__":
    raise SystemExit(main())