# -*- coding: utf-8 -*-
"""Extended route inspector:
- prints URL -> endpoint map
- marks aliases (one endpoint on multiple URLs)
- highlights auto-suffix (guarded) endpoints like *_2, *_3 ...
Run (inside application context):
  python -c "import app; from tools.verify_routes import dump; dump(app.app)"
"""
from __future__ import annotations
from collections import defaultdict
import re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_suffix_re = re.compile(r".*?_(\d+)$")

def dump(app):
    eps = defaultdict(list)
    print("== URL MAP ==")
    for r in app.url_map.iter_rules():
        print(f"{r.rule:40s}  ->  {r.endpoint}")
        eps[r.endpoint].append(r.rule)

    aliases = {ep: rules for ep, rules in eps.items() if len(rules) > 1}
    guarded = {ep: rules for ep, rules in eps.items() if _suffix_re.match(ep)}

    print("\n== ALIASES (endpoint -> urls) ==")
    if not aliases:
        print("(none)")
    else:
        for ep, rules in aliases.items():
            print(f"{ep} => {rules}")

    print("\n== GUARDED (auto-suffixed endpoints) ==")
    if not guarded:
        print("(none)")
    else:
        for ep, rules in guarded.items():
            print(f"{ep} => {rules}")
