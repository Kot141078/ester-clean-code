# -*- coding: utf-8 -*-
"""tools/verify_actions.py - prostoy smok-test reestra deystviy.

What does it do:
  • Pechataet svodku po zaregistrirovannym deystviyam (name, concurrency, taymaut).
  • Probuet vypolnit "discover.list" cherez lokalnyy invoke (esli zaregistrirovan).
  • Vozvraschaet nenulevoy kod vykhoda pri fatalnoy oshibke (dlya CI).

Mosty:
  • Yavnyy: (Operatsii ↔ Diagnostika) bystraya proverka prigodnosti systemy.
  • Skrytye: (Infoteoriya ↔ Nadezhnost) umenshenie neopredelennosti pered zapuskom;
             (Anatomiya ↔ Refleksy) “kolennyy refleks” - korotkiy self-check pered rabotoy.

Zemnoy abzats:
  Utilita kak multimetr: bystro “prozvanivaet” shinu deystviy - zhivo/ne zhivo, skolko “tyanet” parallelno.

# c=a+b"""
from __future__ import annotations

import json
import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    try:
        from modules.thinking.action_registry import list_actions, invoke  # type: ignore
    except Exception as e:
        print(f"juverifs_actionssch failed to import action_registers: ZZF0Z")
        return 2

    try:
        acts = list_actions()
    except Exception as e:
        print(f"[verify_actions] oshibka list_actions: {e}")
        return 3

    print(f"juverifs_actions registered actions: ZZF0Z")
    for it in acts[:50]:
        print(f" - {it.get('name')}  (conc={it.get('concurrency')}, t={it.get('timeout_sec')}, fn={it.get('has_fn')})")

    # We are trying to call the local discovery.list (if it was registered at the start)
    try:
        names = [a.get("name") for a in acts]
        if "discover.list" in names:
            res = invoke("discover.list", {})
            ok = bool(res.get("ok"))
            print(f"[verify_actions] invoke(discover.list) → ok={ok}")
        else:
            print("yuverify_aktionssch discovery.list is not registered yet - I'm missing the call.")
    except Exception as e:
        print(f"[verify_actions] oshibka invoke(discover.list): {e}")
        return 4

    return 0

if __name__ == "__main__":
    sys.exit(main())
# c=a+b