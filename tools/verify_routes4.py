# -*- coding: utf-8 -*-
"""tools/verify_routes.py — proverka konfliktov marshrutov Flask: put/method → ​​unique handler.

Zapusk:
  python tools/verify_routes.py

Vyvodit tablitsu i "OK" libo otchet o kolliziyakh.

MOSTY:
- Yavnyy: (Inzheneriya ↔ Ekspluatatsiya) bystraya samoproverka tselostnosti API.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) rannee vyyavlenie neodnoznachnostey snizhaet entropiyu oshibok.
- Skrytyy #2: (Kibernetika ↔ Kontrol) regulyarnyy self-check pered relizom — prostaya petlya obratnoy svyazi.

ZEMNOY ABZATs:
Skript ne menyaet kod prilozheniya; on lish inspektiruet zaregistrirovannye pravila Flask i ischet dubli.

# c=a+b"""
from __future__ import annotations
import importlib, sys
from typing import Dict, Tuple, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main():
    # We expect that app.po creates a Flask application in the yappy variable
    app_module = importlib.import_module("app")
    app = getattr(app_module, "app", None)
    if app is None:
        print("ERROR: app.py doesn't expose 'app'")
        sys.exit(2)

    seen: Dict[Tuple[str, str], List[str]] = {}
    for rule in app.url_map.iter_rules():
        methods = sorted(m for m in rule.methods if m in ("GET","POST","PUT","DELETE","PATCH"))
        for m in methods:
            key = (m, str(rule))
            seen.setdefault(key, []).append(rule.endpoint)

    conflicts = {k:v for k,v in seen.items() if len(v) > 1}
    print("Registered routes (method path -> endpoint):")
    for (m, path), eps in sorted(seen.items()):
        print(f"{m:6} {path:40} -> {', '.join(eps)}")
    if conflicts:
        print("\nCONFLICTS FOUND:")
        for (m, path), eps in conflicts.items():
            print(f"{m} {path} -> {eps}")
        sys.exit(1)
    print("\nOK: no conflicts")
    sys.exit(0)

if __name__ == "__main__":
    main()