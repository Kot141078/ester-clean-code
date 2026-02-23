# -*- coding: utf-8 -*-
"""
routes/project_share.py — UI/REST «Otpravit proekt» + vkhodyaschiy /ops/inbox/project.

Marshruty:
  • GET  /admin/project/share         — HTML-stranitsa
  • POST /admin/project/share/send    — sformirovat konvert Re otpravit (LAN/Telegram)
  • POST /ops/inbox/project           — priem konverta (validatsiya, anti-repley, zapis v inboks po AB_MODE)

Mosty:
- Yavnyy (Kibernetika v†" Svyaz): odin ekran Re dva refleksa (otpravka/priem).
- Skrytyy 1 (Infoteoriya v†" Kontrakty): envelope + transport_manager v†' bez pravok yadra.
- Skrytyy 2 (Praktika v†" Vezopasnost): v A-rezhime inboks tolko «proslushivaet», bez zapisi na disk.

Zemnoy abzats:
Polzovatel «prikalyvaet bumazhku» (JSON proekta) Re zhmet «Otpravit». Grugoy uzel prinimaet Re, esli razresheno (B),
akkuratno kladet fayl v inboks. Mozg/pamyat/volyu Ester ne trogaem.

# c=a+b
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from flask import Blueprint, Response, jsonify, render_template, request

from modules.transport.project_envelope import make_envelope  # type: ignore
from modules.transport.project_inbox import validate_and_store  # type: ignore
from modules.transport.transport_manager import send_project  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_project_share = Blueprint("project_share", __name__)

SELF_NODE_ID = os.getenv("HOSTNAME") or os.getenv("COMPUTERNAME") or "node"
SELF_BASE = os.getenv("ESTER_HTTP_BASE", "http://127.0.0.1:8080").strip()

@bp_project_share.get("/admin/project/share")
def page_share() -> Response:
    return render_template("project_share.html")

@bp_project_share.post("/admin/project/share/send")
def api_share_send():
    is_json = request.is_json
    mode = (request.form.get("mode") if not is_json else request.json.get("mode", "lan")) or "lan"
    ttl = int((request.form.get("ttl") if not is_json else request.json.get("ttl", 3600)) or 3600)
    try:
        proj_json_raw = (request.form.get("project_json") if not is_json else request.json.get("project_json", "{}")) or "{}"
        project = json.loads(proj_json_raw)
    except Exception:
        return jsonify({"ok": False, "error": "bad-project-json"}), 400

    env = make_envelope(SELF_NODE_ID, SELF_BASE, project=project, ttl=ttl)
    rep = send_project(mode=mode, envelope=env)
    return jsonify({"ok": bool(rep.get("ok")), "send_result": rep, "envelope": env})

@bp_project_share.post("/ops/inbox/project")
def api_inbox_project():
    env = request.get_json(silent=True) or {}
    force_store = request.args.get("store") in ("1", "true")
    rep = validate_and_store(env, force_store=force_store)
    return jsonify(rep), (200 if rep.get("ok") else 400)

def register_project_share(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_project_share)
    if url_prefix:
        pref = Blueprint("project_share_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/project/share")
        def _p():
            return page_share()

        @pref.post("/admin/project/share/send")
        def _ps():
            return api_share_send()

        @pref.post("/ops/inbox/project")
        def _inb():
            return api_inbox_project()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_project_share)
    return app