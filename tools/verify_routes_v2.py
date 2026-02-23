# -*- coding: utf-8 -*-
"""
tools/verify_routes_v2.py — rasshirennaya verifikatsiya Flask-routov i blyuprintov.

MOSTY:
- (Yavnyy) Stroit polnyy spisok pravil, blyuprintov, ischet dublikaty imen i kollizii marshrutov.
- (Skrytyy #1) Pishet otchet JSON po puti data/selfcheck/routes_v2.json.
- (Skrytyy #2) Ne padaet, esli ASGI-prilozhenie nedostupno; vse offlayn.

ZEMNOY ABZATs:
Kak «prozvonka schita»: vidno, kakie avtomaty stoyat, gde dubli i na kakikh liniyakh peregib.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Dict, Any, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

REPORT_DIR = os.path.join("data", "selfcheck")
os.makedirs(REPORT_DIR, exist_ok=True)
REPORT_PATH = os.path.join(REPORT_DIR, "routes_v2.json")

def main() -> int:
    try:
        from app import app  # type: ignore
    except Exception as e:
        print("[verify_v2] can't import app:", e)
        return 2

    # Blyuprinty
    bp_info = []
    name_counts = {}
    for name, bp in app.blueprints.items():
        row = {
            "name": name,
            "import_name": getattr(bp, "import_name", ""),
            "url_prefix": getattr(bp, "url_prefix", ""),
        }
        bp_info.append(row)
        name_counts[name] = name_counts.get(name, 0) + 1

    # Endpointy
    rules = []
    by_rule: Dict[Tuple[str, Tuple[str,...]], List[str]] = {}
    for rule in app.url_map.iter_rules():
        methods = tuple(sorted([m for m in rule.methods if m not in ("HEAD","OPTIONS")]))
        endpoint = rule.endpoint
        rules.append({"rule": str(rule), "endpoint": endpoint, "methods": list(methods)})
        key = (str(rule), methods)
        by_rule.setdefault(key, []).append(endpoint)

    collisions = [{"rule": r, "methods": list(m), "endpoints": eps}
                  for (r, m), eps in by_rule.items() if len(eps) > 1]

    dups = [name for name, n in name_counts.items() if n > 1]

    report: Dict[str, Any] = {
        "ts": int(time.time()),
        "blueprints": sorted(bp_info, key=lambda x: x["name"]),
        "rules": sorted(rules, key=lambda x: x["rule"]),
        "collisions": collisions,
        "duplicate_blueprints": dups,
        "counts": {"blueprints": len(bp_info), "rules": len(rules), "collisions": len(collisions), "dups": len(dups)},
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[verify_v2] blueprints: {report['counts']['blueprints']}, rules: {report['counts']['rules']}, "
          f"collisions: {report['counts']['collisions']}, dups: {report['counts']['dups']}")
    if dups:
        print("[verify_v2] duplicate blueprint names:", ", ".join(dups))
    if report["collisions"]:
        for c in report["collisions"][:10]:
            print(f"[verify_v2] COLLISION {c['rule']} {c['methods']} -> {c['endpoints']}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b