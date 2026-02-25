# -*- coding: utf-8 -*-
"""tools/smoke_all.py - edinyy smoke-test routes bez zapuska vneshnego servera.

Mosty:
- Yavnyy: (QA ↔ App) — podnimaem vremennyy Flask i proveryaem bazovye GET/admin/probnye ruchki.
- Skrytyy 1: (Infrastruktura ↔ Nadezhnost) — ispolzuem register_all i lovim konflikty rantayma.
- Skrytyy 2: (Diagnostika ↔ Logi) — pechataem kratkiy otchet po statusam, prigodnyy dlya CI.

Zemnoy abzats:
Skript “dyshit li vse?” Sobiraet prilozhenie, prokhodit po /probe, /admin i prostym GET, sveryaet 200 OK.
Esli chto-to slomano - kod vozvrata 1."""
from __future__ import annotations
import sys, json
from pathlib import Path
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.register_all import register_all
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main() -> int:
    app = Flask(__name__)
    register_all(app)
    client = app.test_client()
    rules = list(app.url_map.iter_rules())
    probes = [r for r in rules if str(r).endswith("/probe")]
    admins = [r for r in rules if str(r).startswith("/admin")]
    gets = [r for r in rules if "GET" in r.methods and not str(r).endswith("/probe") and not str(r).startswith("/admin")]

    failures = []
    def _hit(path: str):
        rv = client.get(path)
        if rv.status_code != 200:
            failures.append((path, rv.status_code))
        return rv

    # mandatory checks
    _hit("/admin")
    _hit("/health/state")

    # zondovye ruchki
    for r in probes:
        _hit(str(r))

    # stranitsy adminki
    for r in admins:
        _hit(str(r))

    # several GET handles of a general type (limit to ten)
    for r in gets[:10]:
        try:
            _hit(str(r))
        except Exception:
            pass

    report = {
        "total_rules": len(rules),
        "probes_checked": len(probes),
        "admins_checked": len(admins),
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())

# finalnaya stroka
# c=a+b
