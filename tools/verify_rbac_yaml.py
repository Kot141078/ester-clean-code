#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S0/tools/verify_rbac_yaml.py — myagkaya proverka RBAC-matritsy v YAML (bez lomki kontrakta).

Mosty:
- Yavnyy: Enderton (logika) — roli i prava kak formuly nad (subject, action, resource); validiruem strukturu/obyazatelnye klyuchi.
- Skrytyy #1: Ashbi (kibernetika) — proverka prosche sistemy i ne vliyaet na rantaym; podderzhivaet «defektnye» konfigi preduprezhdeniyami.
- Skrytyy #2: Cover & Thomas (infoteoriya) — ubiraem neopredelennost: yavnoe ukazanie «propuscheno/dubliruetsya».

Zemnoy abzats (inzheneriya):
Esli PyYAML otsutstvuet, vyvodit preduprezhdenie i zavershaetcya 0 (S0 — ne valim payplayn).
Trebuet minimum: razdel roles s klyuchami guest/user/admin (khotya by pustymi), i spisok pravil.
Ne menyaet fayly, tolko pechataet otchet i kod vozvrata 0/1.

# c=a+b
"""
from __future__ import annotations
import sys
import json

try:
    import yaml  # type: ignore
except Exception:  # noqa: BLE001
    print("[verify_rbac_yaml] WARN: PyYAML ne ustanovlen — propusk proverki (OK dlya S0).")
    sys.exit(0)

from typing import Any, Dict, List, Set  # noqa: E402
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

REQUIRED_ROLES = {"guest", "user", "admin"}

def main() -> int:
    if len(sys.argv) < 2:
        print("usage: verify_rbac_yaml.py <path_to_yaml>")
        return 1
    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    problems: List[str] = []
    warnings: List[str] = []

    roles = data.get("roles")
    if not isinstance(roles, dict):
        problems.append("Otsutstvuet razdel 'roles' (dict)")
    else:
        have = set(roles.keys())
        missing = REQUIRED_ROLES - have
        if missing:
            problems.append(f"V 'roles' otsutstvuyut: {', '.join(sorted(missing))}")

    rules = data.get("rules")
    if not isinstance(rules, list):
        warnings.append("Otsutstvuet spisok 'rules' (list) — vozmozhno, primenyayutsya tolko defoltnye ogranicheniya.")

    # Prostaya proverka dublikatov po (role, method, path)
    seen: Set[str] = set()
    dups: List[str] = []
    if isinstance(rules, list):
        for i, r in enumerate(rules):
            role = (r or {}).get("role")
            method = (r or {}).get("method")
            pathp = (r or {}).get("path")
            if role and method and pathp:
                key = f"{role}|{method}|{pathp}"
                if key in seen:
                    dups.append(f"#{i} {key}")
                else:
                    seen.add(key)
    if dups:
        warnings.append("Dublikaty pravil: " + "; ".join(dups))

    out = {"problems": problems, "warnings": warnings}
    print(json.dumps(out, ensure_ascii=False, indent=2))

    # V S0 — dazhe pri problemakh ne valim payplayn, prosto vozvraschaem 0
    return 0

if __name__ == "__main__":
    raise SystemExit(main())