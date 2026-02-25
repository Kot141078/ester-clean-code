# -*- coding: utf-8 -*-
"""modules/thinking/actions_garage.py - eksheny “voli” dlya Laboratorii-Garazha.

Mosty:
- Yavnyy: (Mysli ↔ Garazh) korotkie komandy na ves tsikl: skanirovat/import→otsenka→offer→skelet→schet→portfolio→flot.
- Skrytyy #1: (RBAC/Politiki) uvazhaet obschuyu sistemu roley cherez REST ili lokalno.
- Skrytyy #2: (Memory ↔ Profile) modulnye operatsii uzhe logiruyutsya.
- Skrytyy #3: (Ekonomika ↔ CostFence) legkie deystviya stoyat deshevo; tyazhelye - luchshe vyzyvat pod pillyuley cherez REST.

Zemnoy abzats:
Mozg otdaet prikazy - “vozmi zayavku, otseni, predlozhi, soberi karkas, vypishi schet, razday zadachi” - i konveyer rabotaet. Dali Ester udochku: vidit rabotu - gotovit zayavku - pokazyvaet lending - vystavlyaet schet, vse s fallback dlya resilience.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    import json, urllib.request

    GARAGE_URL = os.getenv("GARAGE_URL", "http://127.0.0.1:8000")

    def _post(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            url = GARAGE_URL + endpoint
            data = json.dumps(payload or {}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=21600) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            return {"ok": False, "error": f"server_down: {str(e)}"}

    # Local actions (from the first)
    def a_scan(args: Dict[str, Any]):
        from modules.garage.jobs import scan
        return scan()
    register("garage.jobs.scan", {}, {"ok": "bool", "items": "list"}, 5, a_scan)

    def a_prop_local(args: Dict[str, Any]):
        from modules.garage.core import get_project
        from modules.garage.proposal import make
        pr = get_project(str(args.get("id", "")))
        if not pr.get("ok"): return {"ok": False, "error": "project_not_found"}
        return make(pr["project"], dict(args.get("job") or {}), str(args.get("client", "Client")), float(args.get("budget", 0.0)), str(args.get("currency", "EUR")), args.get("rate"), args.get("hours"), args.get("delivery"))
    register("garage.proposal.make", {"id": "str", "job": "dict", "client": "str"}, {"ok": "bool"}, 20, a_prop_local)

    def a_site(args: Dict[str, Any]):
        from modules.garage.core import get_project
        from modules.garage.sitegen import build_project_site
        pr = get_project(str(args.get("id", "")))
        if not pr.get("ok"): return {"ok": False, "error": "project_not_found"}
        return build_project_site(pr["project"], str(args.get("theme", "clean")))
    register("garage.site.build", {"id": "str", "theme": "str"}, {"ok": "bool"}, 10, a_site)

    def a_invoice_local(args: Dict[str, Any]):
        from modules.garage.invoice import make_invoice
        return make_invoice(dict(args.get("sender") or {}), dict(args.get("client") or {}), list(args.get("items") or []), str(args.get("currency", "EUR")), bool(args.get("make_pain001", False)), str(args.get("end_to_end", "")), str(args.get("purpose", "")))
    register("garage.invoice.draft", {"sender": "dict", "client": "dict", "items": "list"}, {"ok": "bool"}, 8, a_invoice_local)

    # REST actions (from the second, with false ones where possible)
    def a_import(args: Dict[str, Any]): return _post("/garage/job/import", dict(args or {}))
    register("garage.job.import", {"id": "str"}, {"ok": "bool"}, 1, a_import)

    def a_score(args: Dict[str, Any]): return _post("/garage/job/score", {"id": str(args.get("id", ""))})
    register("garage.job.score", {"id": "str"}, {"ok": "bool"}, 1, a_score)

    def a_prop(args: Dict[str, Any]): return _post("/garage/proposal/build", {"id": str(args.get("id", "")), "include_scaffold": bool(args.get("include_scaffold", False))})
    register("garage.proposal.build", {"id": "str", "include_scaffold": "bool"}, {"ok": "bool"}, 3, a_prop)

    def a_scf(args: Dict[str, Any]): return _post("/garage/project/scaffold", {"name": str(args.get("name", "")), "stack": str(args.get("stack", "python-web"))})
    register("garage.project.scaffold", {"name": "str", "stack": "str"}, {"ok": "bool"}, 2, a_scf)

    def a_inv(args: Dict[str, Any]):
        rep = _post("/garage/invoice/make", {"invoice_id": str(args.get("invoice_id", "INV-TEST")), "client": dict(args.get("client") or {}), "items": list(args.get("items") or []), "currency": str(args.get("currency", "EUR"))})
        if not rep.get("ok"):  # fallback na lokalnyy
            return a_invoice_local(args)
        return rep
    register("garage.invoice.make", {"invoice_id": "str"}, {"ok": "bool"}, 2, a_inv)

    def a_port(args: Dict[str, Any]):
        try:
            with urllib.request.urlopen(GARAGE_URL + "/garage/portfolio/list", timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            return {"ok": False, "error": f"server_down: {str(e)}"}
    register("garage.portfolio.list", {}, {"ok": "bool"}, 1, a_port)

    def a_fleet(args: Dict[str, Any]): return _post("/garage/fleet/assign", {"tasks": list(args.get("tasks") or []), "peers": list(args.get("peers") or [])})
    register("garage.fleet.assign", {"tasks": "list", "peers": "list"}, {"ok": "bool"}, 4, a_fleet)

    # New extension: EBS list for monitoring
    def a_jobs_list(args: Dict[str, Any]):
        try:
            with urllib.request.urlopen(GARAGE_URL + "/garage/jobs/list", timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            return {"ok": False, "error": f"server_down: {str(e)}"}
    register("garage.jobs.list", {}, {"ok": "bool", "items": "list"}, 1, a_jobs_list)

# _reg()




