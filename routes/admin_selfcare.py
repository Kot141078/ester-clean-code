# -*- coding: utf-8 -*-
"""
routes/admin_selfcare.py - panel Self-Care: status planirovschika, pravila, ruchnoy zapusk, tiket.

Marshruty:
  • GET  /admin/selfcare              - HTML
  • GET  /admin/selfcare/status       - ENV, intervaly, last history lines, rules summary
  • POST /admin/selfcare/run_once     - vruchnuyu: otchet + plan pravil + (v B) avto-pochinka
  • POST /admin/selfcare/rules        - {op:get|set, rules?}
  • POST /admin/selfcare/ticket       - {mount?} → sobrat tiket (i kopiya na USB)

Mosty:
- Yavnyy (UX ↔ Ekspluatatsiya): edinyy ekran dlya «posmotret/izmenit/zapustit».
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): vse v JSON, dry-run v A, otchety v istoriyu.
- Skrytyy 2 (Praktika ↔ Sovmestimost): chistyy stdlib; yadro Ester ne trogaem.

Zemnoy abzats:
Eto «pult ukhoda»: proverit seychas, popravit pravila i srazu sobrat materialy dlya tiketa.

# c=a+b
"""
from __future__ import annotations
import json, os, time
from pathlib import Path
from typing import Any, Dict, List
from flask import Blueprint, jsonify, render_template, request

from modules.selfcheck.health_probe import build_report  # type: ignore
from modules.selfcare.rules import load_rules, save_rules, eval_rules  # type: ignore
from modules.selfcare.archive import build_ticket  # type: ignore
from modules.selfcheck.auto_fix import restart_sidecar, clear_inboxes, rebuild_indices, rebind_lmstudio, rescan_usb_once  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_sc = Blueprint("admin_selfcare", __name__)

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
HIST_DIR = STATE_DIR / "diagnostics" / "history"
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _read_tail(limit: int = 50) -> List[Dict[str, Any]]:
    out=[]
    for p in sorted(HIST_DIR.glob("*.ndjson"))[-3:]:
        try:
            lines = p.read_text(encoding="utf-8").splitlines()[-max(1,limit//3):]
            for ln in lines:
                try: out.append(json.loads(ln))
                except Exception: continue
        except Exception:
            continue
    return out[-limit:]

@bp_sc.get("/admin/selfcare")
def page():
    return render_template("admin_selfcare.html", ab=AB)

@bp_sc.get("/admin/selfcare/status")
def status():
    env = {
        "AB_MODE": AB,
        "SELFCARE_ENABLE": os.getenv("SELFCARE_ENABLE","0"),
        "SELFCARE_INTERVAL_MIN": os.getenv("SELFCARE_INTERVAL_MIN","30"),
        "SELFCARE_DEEP_EVERY": os.getenv("SELFCARE_DEEP_EVERY","4"),
        "SELFCARE_AUTOFIX_ENABLE": os.getenv("SELFCARE_AUTOFIX_ENABLE","1"),
    }
    rules = load_rules()
    return jsonify({"ok": True, "env": env, "rules_summary": {"count": len(rules.get("items",[]))}, "tail": _read_tail(40)})

@bp_sc.post("/admin/selfcare/run_once")
def run_once():
    rep = build_report(deep=True)
    plan = eval_rules(rep)
    actions = plan.get("plan", [])
    results=[]
    if AB == "B" and os.getenv("SELFCARE_AUTOFIX_ENABLE","1") == "1":
        # ispolnim kak v planirovschike
        for item in actions:
            for a in item.get("actions", []):
                act=a.get("action")
                if act=="restart_sidecar": results.append({"restart_sidecar": restart_sidecar()})
                if act=="clear_inboxes": results.append({"clear_inboxes": clear_inboxes()})
                if act=="rebuild_indices": results.append({"rebuild_indices": rebuild_indices()})
                if act=="rebind_lmstudio": results.append({"rebind_lmstudio": rebind_lmstudio()})
                if act=="rescan_usb_once": results.append({"rescan_usb_once": rescan_usb_once()})
    return jsonify({"ok": True, "report": rep, "plan": plan, "results": results, "ab": AB})

@bp_sc.post("/admin/selfcare/rules")
def rules():
    body = request.get_json(silent=True) or {}
    op = (body.get("op") or "get").strip()
    if op == "set":
        rules = body.get("rules") or {}
        return jsonify(save_rules(rules))
    return jsonify(load_rules())

@bp_sc.post("/admin/selfcare/ticket")
def ticket():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip() or None
    return jsonify(build_ticket(copy_to_mount=mount))

def register_admin_selfcare(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_sc)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_selfcare_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/selfcare")
        def _p(): return page()

        @pref.get("/admin/selfcare/status")
        def _s(): return status()

        @pref.post("/admin/selfcare/run_once")
        def _r(): return run_once()

        @pref.post("/admin/selfcare/rules")
        def _ru(): return rules()

        @pref.post("/admin/selfcare/ticket")
        def _t(): return ticket()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_sc)
    return app