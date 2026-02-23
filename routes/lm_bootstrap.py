# -*- coding: utf-8 -*-
"""
routes/lm_bootstrap.py - UI/REST «Bootstrap LM Studio».

Marshruty:
  • GET  /admin/lm_bootstrap                 - HTML
  • GET  /admin/lm_bootstrap/status          - OS, installyatory, aliases
  • POST /admin/lm_bootstrap/plan_install    - plan ustanovki
  • POST /admin/lm_bootstrap/run_install     - zapusk ustanovki (AB=B)
  • POST /admin/lm_bootstrap/check_endpoint  - {endpoint}
  • POST /admin/lm_bootstrap/auto_bind       - {alias, endpoint, model}
  • POST /admin/lm_bootstrap/smoke_chat      - {endpoint, model, prompt?, max_tokens?, temperature?}

Mosty:
- Yavnyy (UX ↔ Resursy): edinyy ekran dlya «ustanovit → proverit API → privyazat alias → smoke».
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): plan pered deystviem; minimalnye taymauty i obemy.
- Skrytyy 2 (Praktika ↔ Sovmestimost): stdlib, drop-in; yadro Ester ne trogaem.

Zemnoy abzats:
Eto «knopka zapuska»: vse, chto nuzhno dlya LM Studio, sobrano v odnom meste - bez kopaniya v konfigakh.

# c=a+b
"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.lm.bootstrap import detect_os, list_installers, plan_install, run_install, check_endpoint, auto_bind, list_aliases, smoke_chat  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_lmb = Blueprint("lm_bootstrap", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_lmb.get("/admin/lm_bootstrap")
def page():
    return render_template("lm_bootstrap.html", ab=AB)

@bp_lmb.get("/admin/lm_bootstrap/status")
def status():
    return jsonify({
        "ok": True, "ab": AB,
        "system": detect_os(),
        "installers": list_installers(),
        "aliases": list_aliases()
    })

@bp_lmb.post("/admin/lm_bootstrap/plan_install")
def api_plan_install():
    return jsonify(plan_install())

@bp_lmb.post("/admin/lm_bootstrap/run_install")
def api_run_install():
    return jsonify(run_install())

@bp_lmb.post("/admin/lm_bootstrap/check_endpoint")
def api_check():
    body = request.get_json(silent=True) or {}
    ep = (body.get("endpoint") or "").strip()
    if not ep: return jsonify({"ok": False, "error": "endpoint required"}), 400
    return jsonify(check_endpoint(ep))

@bp_lmb.post("/admin/lm_bootstrap/auto_bind")
def api_bind():
    body = request.get_json(silent=True) or {}
    alias = (body.get("alias") or "").strip()
    ep = (body.get("endpoint") or "").strip()
    model = (body.get("model") or "").strip()
    if not alias or not ep or not model:
        return jsonify({"ok": False, "error": "alias/endpoint/model required"}), 400
    return jsonify(auto_bind(alias, ep, model))

@bp_lmb.post("/admin/lm_bootstrap/smoke_chat")
def api_smoke():
    body = request.get_json(silent=True) or {}
    ep = (body.get("endpoint") or "").strip()
    model = (body.get("model") or "").strip()
    prompt = str(body.get("prompt") or "ping")
    maxtok = int(body.get("max_tokens", 8))
    temp = float(body.get("temperature", 0.0))
    if not ep or not model:
        return jsonify({"ok": False, "error": "endpoint/model required"}), 400
    return jsonify(smoke_chat(ep, model, prompt=prompt, max_tokens=maxtok, temperature=temp))
# c=a+b


def register(app):
    app.register_blueprint(bp_lmb)
    return app