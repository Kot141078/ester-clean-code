# -*- coding: utf-8 -*-
"""
routes/github_publish_routes.py - publikatsiya «public-safe» v GitHub (po zhelaniyu).

MOSTY:
- (Yavnyy) GET /publish/status - sostoyanie eksporta; POST /publish/run {dry_run, push}
- (Skrytyy #1) Delegiruet sborku v tools/publish/build_public.py (A/B-sloty sanitizatsii).
- (Skrytyy #2) Delegiruet push v tools/publish/github_publish.py pri push=true (bezopasno, offlayn-gotovo).

ZEMNOY ABZATs:
Knopka «upakovat i vylozhit»: sobiraem akkuratnyy publichnyy nabor i, esli nado, pushim na GitHub.

# c=a+b
"""
from __future__ import annotations
import os, json, time, glob
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("github_publish", __name__, url_prefix="/publish")

def register(app):
    app.register_blueprint(bp)

def _last_exports(n=5):
    os.makedirs("data/public_export", exist_ok=True)
    files = sorted(glob.glob("data/public_export/*.zip"), key=os.path.getmtime, reverse=True)[:n]
    return [{"file": os.path.basename(f), "bytes": os.path.getsize(f)} for f in files]

@bp.get("/status")
def status():
    return jsonify({
        "ok": True,
        "exports": _last_exports(),
        "repo": os.getenv("GITHUB_REPO",""),
        "branch": os.getenv("GITHUB_BRANCH","public-safe"),
        "dry_default": True
    })

@bp.post("/run")
def run():
    body = request.get_json(silent=True) or {}
    dry = bool(body.get("dry_run", True))
    push = bool(body.get("push", False))

    # 1) Sborka public-safe
    try:
        from tools.publish.build_public import build_public  # type: ignore
        res = build_public(dry_run=dry)
    except Exception as e:
        return jsonify({"ok": False, "stage": "build", "error": str(e)}), 500

    if not res.get("ok"):
        return jsonify(res), 500

    # 2) Push (optsionalno)
    if push and not dry:
        try:
            from tools.publish.github_publish import push_repo  # type: ignore
            pub = push_repo(res["workdir"])
            return jsonify({"ok": pub.get("ok", False), "build": res, "git": pub})
        except Exception as e:
            return jsonify({"ok": False, "stage": "push", "build": res, "error": str(e)}), 500

    return jsonify({"ok": True, "build": res})
# c=a+b