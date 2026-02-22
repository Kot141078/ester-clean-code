# -*- coding: utf-8 -*-
"""
modules/thinking/actions_selfevo_market_sos_portfolio.py — eksheny «voli» dlya SelfEvo/Portfolio/Gigs/SOS.

Mosty:
- Yavnyy: (Mysli ↔ Proekty/Rynok/Bezopasnost) korotkie komandy na vse klyuchevoe.
- Skrytyy #1: (Profile ↔ Prozrachnost) vse upravlyaemye shagi vidny v zhurnale.
- Skrytyy #2: (Planirovschik ↔ Avtonomiya) mozhno zapustit po kronu ili sobytiyam.

Zemnoy abzats:
Komanda — i kuznitsa sozdaet modul, vitrina obnovlyaetsya, vakansiya razbiraetsya, signal uletaet po provodam.

# c=a+b
"""
from __future__ import annotations
import json, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def _get(path: str, timeout: int=20):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    def _post(path: str, payload: dict, timeout: int=120):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    # SelfEvo
    register("selfevo.forge.dryrun", {"path":"str","kind":"str","name":"str","desc":"str","export":"str"}, {"ok":"bool"}, 2,
             lambda a: _post("/selfevo/forge/dryrun", {"path": a.get("path",""), "kind": a.get("kind","route"), "name": a.get("name","new_module"), "desc": a.get("desc",""), "export": a.get("export","routes")}))
    register("selfevo.forge.apply", {"path":"str","code":"str","register_after":"bool"}, {"ok":"bool"}, 2,
             lambda a: _post("/selfevo/forge/apply", {"path": a.get("path",""), "code": a.get("code",""), "register_after": bool(a.get("register_after",False))}))
    register("selfevo.forge.list", {}, {"ok":"bool"}, 1, lambda a: _get("/selfevo/forge/list"))

    # Portfolio
    register("garage.portfolio.build", {}, {"ok":"bool"}, 1, lambda a: _post("/garage/portfolio/build", {}))
    register("garage.portfolio.status", {}, {"ok":"bool"}, 1, lambda a: _get("/garage/portfolio/status"))

    # Gigs
    register("market.gigs.scan", {"items":"list"}, {"ok":"bool"}, 2, lambda a: _post("/market/gigs/scan", {"items": list(a.get("items") or [])}))
    register("market.gigs.apply", {"job":"object","profile":"object","tone":"str"}, {"ok":"bool"}, 1, lambda a: _post("/market/gigs/apply", {"job": dict(a.get("job") or {}), "profile": dict(a.get("profile") or {}), "tone": a.get("tone","concise")}))
    register("market.gigs.list", {"limit":"number"}, {"ok":"bool"}, 1, lambda a: _get(f"/market/gigs/list?limit={int(a.get('limit',50))}"))

    # SOS
    register("sos.config.set", {"webhooks":"list","contacts":"object"}, {"ok":"bool"}, 2, lambda a: _post("/sos/config/set", {"webhooks": list(a.get("webhooks") or []), "contacts": dict(a.get("contacts") or {})}))
    register("sos.config.get", {}, {"ok":"bool"}, 1, lambda a: _get("/sos/config/get"))
    register("sos.trigger", {"kind":"str","note":"str"}, {"ok":"bool"}, 1, lambda a: _post("/sos/trigger", {"kind": a.get("kind","notify"), "note": a.get("note","")}))
_reg()
# c=a+b