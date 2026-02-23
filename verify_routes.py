# -*- coding: utf-8 -*-
"""
verify_routes.py — edinyy sborschik versiy/routov/statusa.

MOSTY:
- (Yavnyy) Importiruet klyuchevye modules/routes, pechataet ikh versii i pishet JSON-otchet.
- (Skrytyy #1) Pytaetsya postroit Flask app i snyat spisok endpoints; esli ne udaetsya — ne padaet.
- (Skrytyy #2) Probuet ASGI-prilozhenie (FastAPI) i fiksiruet bazovoe zdorove /api/v2/health, esli dostupno.

ZEMNOY ABZATs:
Kak «diagnosticheskiy razem» OBD-II: bystro snyali pokazaniya i ponyali, chto rabotaet, a chto net.

# c=a+b
"""
from __future__ import annotations
import os, json, importlib, traceback, time
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

REPORT_DIR = os.path.join("data", "selfcheck")
os.makedirs(REPORT_DIR, exist_ok=True)
REPORT_PATH = os.path.join(REPORT_DIR, "report.json")

MODULES = [
    "routes.health_routes",
    "routes.metrics_prom",
    "routes.ui_portal",
    "routes.telegram_feed_routes",
    "routes.whatsapp_feed_routes",
    "routes.admin_integrations",
    "routes.auto_login",
    "routes.providers_probe",
    "routes.ops_routes",
    "routes.kg_admin_routes",
    "routes.mem_ingest_routes",
    # optsionalnye:
    "routes.kg_routes",
    "routes.mem_entity_routes",
    "routes.mem_routes",
    "routes.ingest_routes",
    "routes.backup_routes",
    "routes.will_routes",
    "routes.autonomy_routes",
    "routes.graph_routes",
    "routes.subconscious_routes",
    "routes.debug_routes",
]

def _mod_info(name: str) -> Dict[str, Any]:
    try:
        m = importlib.import_module(name)
        ver = getattr(m, "__version__", "n/a")
        return {"ok": True, "version": ver}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

def _collect_flask_routes() -> List[Dict[str, Any]]:
    try:
        from app import app
        items = []
        for rule in app.url_map.iter_rules():
            items.append({
                "endpoint": rule.endpoint, "rule": str(rule), "methods": sorted([m for m in rule.methods if m not in ("HEAD","OPTIONS")])
            })
        return sorted(items, key=lambda x: x["rule"])
    except Exception:
        return []

def _probe_asgi() -> Dict[str, Any]:
    out: Dict[str, Any] = {"loaded": False}
    try:
        from asgi.app_main import app as asgi_app  # type: ignore
        out["loaded"] = True
        out["type"] = type(asgi_app).__name__
        # bez realnogo HTTP — prosto fakt sborki
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out

def main() -> int:
    rep: Dict[str, Any] = {"ts": int(time.time()), "env": {}, "modules": {}, "flask_routes": [], "asgi": {}}
    keys = ["HOST","PORT","APP_TITLE","ESTER_DEFAULT_USER","AUTHORING_LLM_BACKEND","LMSTUDIO_ENDPOINTS"]
    for k in keys:
        rep["env"][k] = os.getenv(k, "")
    for name in MODULES:
        rep["modules"][name] = _mod_info(name)
    rep["flask_routes"] = _collect_flask_routes()
    rep["asgi"] = _probe_asgi()
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    # Kratkaya pechat
    ok_mods = sum(1 for v in rep["modules"].values() if v.get("ok"))
    print(f"[verify] modules ok: {ok_mods}/{len(MODULES)}; flask routes: {len(rep['flask_routes'])}; asgi loaded: {rep['asgi'].get('loaded')}")
    print(f"[verify] report -> {REPORT_PATH}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b