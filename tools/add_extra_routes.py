# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

NEEDED = [
    "routes.favicon_routes_alias",
    "routes.portal_routes_alias",
    "app_plugins.autoregister_compat_pydantic",
    "routes.jwt_owner_routes"
]

def main() -> int:
    base = os.getcwd()
    path = os.path.join(base, "data", "app", "extra_routes.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.isfile(path):
        try:
            arr = json.load(open(path, "r", encoding="utf-8"))
            if not isinstance(arr, list): raise ValueError("not a list")
        except Exception:
            arr = []
    else:
        arr = []
    for item in NEEDED:
        if item not in arr:
            arr.append(item)
    json.dump(arr, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps({ "ok": True, "file": path, "count": len(arr) }, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())