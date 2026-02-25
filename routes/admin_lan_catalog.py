# -*- coding: utf-8 -*-
"""routes/admin_lan_catalog.py - UI/API dlya LAN Catalog Sync (read-only) + generatsiya USB-ocheredi iz plana.

Added:
  • POST /admin/lan_catalog/plan_to_usb - {plan, stage?, clean_jobs?, noop_for_remote?} → pishet ESTER/jobs/*.json (+payloads/*)

Politika:
  • Rabotaet tolko esli LAN_PLAN2USB_ENABLE=1.
  • Avtoopredelyaet fleshku cherez modules.usb_runner.jobs.detect_usb_root().
  • AB_MODE=A - dry-run: nichego ne pishem, tolko prevyu otveta.

# c=a+b"""
from __future__ import annotations
import os
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

from modules.lan_catalog.peers import list_peers, load_catalogs  # type: ignore
from modules.lan_catalog.exporter import build_local_catalog  # type: ignore
from modules.lan_catalog.plan_to_jobs import generate_usb_queue  # type: ignore
from modules.usb_runner.jobs import detect_usb_root  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_lan_catalog", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _recommend_dest(kind: str, name: str) -> str:
    base = os.path.expanduser(os.getenv("USB_CATALOG_DEFAULT_DEST","~/.ester/imports")).rstrip("/")
    sub = "datasets" if kind=="folder" else ("models" if kind=="model" else "files")
    return f"{base}/{sub}/{name}"

@bp.get("/admin/lan_catalog")
def page():
    return render_template("admin_lan_catalog.html", ab=AB)

@bp.get("/admin/lan_catalog/status")
def status():
    peers = list_peers()
    cats = load_catalogs()
    local = build_local_catalog({})
    return jsonify({"ok": True, "ab": AB, "peers": peers.get("peers") or [], "local": local, "items": cats.get("items") or []})

@bp.post("/admin/lan_catalog/plan")
def plan():
    body = request.get_json(silent=True) or {}
    nodes = [str(x) for x in (body.get("nodes") or []) if str(x).strip()]
    kinds = set([str(x).strip() for x in (body.get("kinds") or []) if str(x).strip()])
    tags  = set([str(x).strip() for x in (body.get("tags") or []) if str(x).strip()])

    cats = load_catalogs().get("items") or []
    out = []
    for it in cats:
        if nodes and (it.get("_source_node") not in nodes): 
            continue
        kind = it.get("kind") or "file"
        name = (it.get("title") or it.get("uid") or "item")
        if kinds and (kind not in kinds):
            continue
        if tags and not (set(it.get("tags") or []) & tags):
            continue
        out.append({
            "source_node": it.get("_source_node"),
            "uid": it.get("uid"),
            "kind": kind,
            "title": name,
            "lmstudio_alias": it.get("lmstudio_alias"),
            "recommend_dest": _recommend_dest(kind, name)
        })
    return jsonify({"ok": True, "plan": {"schema":"ester.lan.import.plan/1", "ab": AB, "count": len(out), "items": out}})

@bp.post("/admin/lan_catalog/plan_to_usb")
def plan_to_usb():
    if os.getenv("LAN_PLAN2USB_ENABLE","1") != "1":
        return jsonify({"ok": False, "error": "disabled"}), 403
    usb = detect_usb_root()
    if not usb:
        return jsonify({"ok": False, "error": "usb-not-found"}), 404
    body = request.get_json(silent=True) or {}
    plan = body.get("plan") or {}
    opts = {
        "stage": bool(body.get("stage", os.getenv("LAN_PLAN2USB_STAGE","1")=="1")),
        "clean_jobs": bool(body.get("clean_jobs", os.getenv("LAN_PLAN2USB_CLEAN","0")=="1")),
        "noop_for_remote": bool(body.get("noop_for_remote", os.getenv("LAN_PLAN2USB_NOOP_REMOTE","1")=="1")),
    }
    res = generate_usb_queue(plan, usb, opts)
    return jsonify({"ok": True, "usb": str(usb), "opts": opts, "result": res})

def register_admin_lan_catalog(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_lan_catalog_pref", __name__, url_prefix=url_prefix)
        @pref.get("/admin/lan_catalog")
        def _p(): return page()
        @pref.get("/admin/lan_catalog/status")
        def _s(): return status()
        @pref.post("/admin/lan_catalog/plan")
        def _pl(): return plan()
        @pref.post("/admin/lan_catalog/plan_to_usb")
        def _pu(): return plan_to_usb()
        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app