# -*- coding: utf-8 -*-
"""routes/admin_diagnostics.py - expandedno: dry-diff kolliziy/perezapisey i plan zaschity jobs.

Added:
  • POST /admin/diagnostics/collisions_scan - polnyy otchet po jobs (perezapisi/multizapisi) + zaschitnyy plan
  • POST /admin/diagnostics/collisions_apply - {plan} → patch args.dest v job-faylakh (AB=A → prevyu)

Mosty:
- Yavnyy (Plan→Deystvie): otchet → patch zadach, ne trogaya ranner i dannye.
- Skrytyy 1 (Infoteoriya): metki overwrite_same/diff i multiwrite_same/diff - chetkaya tipizatsiya stsenariev.
- Skrytyy 2 (Praktika): offlayn, stdlib, zapis ogranichena job-faylami v AB=B.

Zemnoy abzats:
This is “stop-kadr pered razgruzkoy”: vidim, chto imenno zatronetsya, i pri neobkhodimosti otvodim potok v bezopasnoe mesto.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.diagnostics.whitelist_check import (  # uzhe byli
    get_whitelist, scan_usb_jobs, scan_usb_catalog, synthesize_lan_plan,
    check_lmstudio_aliases, apply_alias_fixes
)
# novoe:
from modules.diagnostics.collision_check import scan_collisions, build_protect_plan, apply_protect_plan  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_diagnostics", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp.get("/admin/diagnostics")
def page():
    return render_template("admin_diagnostics.html", ab=AB)

@bp.get("/admin/diagnostics/status")
def status():
    wl = get_whitelist()
    try:
        from modules.portable.env import detect_portable_root  # type: ignore
        usb = detect_portable_root(None)
        usb_s = (str(usb) if usb else None)
    except Exception:
        usb_s = None
    return jsonify({"ok": True, "ab": AB, "whitelist": wl, "usb": usb_s})

@bp.post("/admin/diagnostics/scan")
def scan():
    wl = get_whitelist()
    jobs = scan_usb_jobs()
    cat = scan_usb_catalog()
    lan = synthesize_lan_plan()
    aliases = check_lmstudio_aliases()
    bad_jobs = [x for x in jobs.get("items") or [] if (not x.get("dest_ok") or not x.get("src_ok"))]
    bad_cat  = [x for x in cat.get("items") or [] if not x.get("dest_ok")]
    bad_lan  = [x for x in lan.get("items") or [] if not x.get("rec_ok")]
    bad_alias = [x for x in aliases.get("items") or [] if not x.get("exists")]
    summary = {"jobs_bad": len(bad_jobs), "catalog_bad": len(bad_cat), "lan_rec_bad": len(bad_lan), "aliases_bad": len(bad_alias)}
    return jsonify({"ok": True, "ab": AB,
                    "whitelist": wl, "jobs": jobs, "catalog": cat, "lan": lan,
                    "aliases": aliases, "summary": summary})

@bp.post("/admin/diagnostics/alias_fix")
def alias_fix():
    body = request.get_json(silent=True) or {}
    mapping = body.get("mapping") or {}
    res = apply_alias_fixes(mapping)
    return jsonify({"ok": True, "ab": AB, "result": res})

# ---- Novye endpointy ----

@bp.post("/admin/diagnostics/collisions_scan")
def collisions_scan():
    rep = scan_collisions()
    if not rep.get("ok"):
        return jsonify(rep), 400
    plan = build_protect_plan(rep)
    return jsonify({"ok": True, "ab": AB, "report": rep, "protect_plan": plan})

@bp.post("/admin/diagnostics/collisions_apply")
def collisions_apply():
    body = request.get_json(silent=True) or {}
    plan = body.get("plan") or {}
    res = apply_protect_plan(plan)
    code = 200 if res.get("ok") else 400
    return jsonify({"ok": bool(res.get("ok")), "ab": AB, "result": res}), code

def register_admin_diagnostics(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_diagnostics_pref", __name__, url_prefix=url_prefix)
        @pref.get("/admin/diagnostics")
        def _p(): return page()
        @pref.get("/admin/diagnostics/status")
        def _s(): return status()
        @pref.post("/admin/diagnostics/scan")
        def _sc(): return scan()
        @pref.post("/admin/diagnostics/alias_fix")
        def _af(): return alias_fix()
        @pref.post("/admin/diagnostics/collisions_scan")
        def _cs(): return collisions_scan()
        @pref.post("/admin/diagnostics/collisions_apply")
        def _ca(): return collisions_apply()
        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app