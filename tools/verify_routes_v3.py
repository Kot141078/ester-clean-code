# -*- coding: utf-8 -*-
"""
tools/verify_routes_v3.py — edinyy otchet po Flask+FastAPI.

MOSTY:
- (Yavnyy) Damp blyuprintov/pravil Flask i routov FastAPI (esli importiruetsya).
- (Skrytyy #1) Pishet JSON-otchet v data/selfcheck/routes_v3.json.
- (Skrytyy #2) Ne zavisit ot nalichiya FastAPI — sektsiya asgi pustaya, esli net.

ZEMNOY ABZATs:
Odin «ommetr» na dve shiny: Flask i ASGI na odnom liste — udobno lovit konflikty i probely.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

REPORT_DIR = os.path.join("data", "selfcheck")
os.makedirs(REPORT_DIR, exist_ok=True)
REPORT = os.path.join(REPORT_DIR, "routes_v3.json")

def _flask_dump() -> Dict[str, Any]:
    try:
        from app import app  # type: ignore
    except Exception as e:
        return {"error": f"flask import: {e}"}
    bps = [{"name": n, "import": getattr(b,"import_name",""), "prefix": getattr(b,"url_prefix","")} for n,b in app.blueprints.items()]
    rules = []
    for r in app.url_map.iter_rules():
        ms = sorted([m for m in r.methods if m not in ("HEAD","OPTIONS")])
        rules.append({"rule": str(r), "endpoint": r.endpoint, "methods": ms})
    return {"blueprints": bps, "rules": rules}

def _asgi_dump() -> Dict[str, Any]:
    try:
        from asgi.synergy_api_v2 import app as asgi_app  # type: ignore
    except Exception as e1:
        try:
            from asgi.app_main import app as asgi_app  # type: ignore
        except Exception as e2:
            return {"error": f"asgi import: {e1} / {e2}"}
    try:
        # FastAPI: app.routes soderzhit obekty so svoystvami .path, .methods
        routes = []
        for r in getattr(asgi_app, "routes", []):
            path = getattr(r, "path", None) or getattr(r, "path_format", None) or str(r)
            methods = sorted(list(getattr(r, "methods", set()) or []))
            routes.append({"path": path, "methods": methods})
        return {"ok": True, "routes": routes}
    except Exception as e:
        return {"error": f"asgi scan: {e}"}

def main() -> int:
    rep = {"ts": int(time.time()), "flask": _flask_dump(), "asgi": _asgi_dump()}
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"[verify_v3] report -> {REPORT}")
    fcnt = len(rep.get("flask",{}).get("rules",[]))
    acnt = len(rep.get("asgi",{}).get("routes",[]))
    print(f"[verify_v3] flask rules: {fcnt}, asgi routes: {acnt}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b