# -*- coding: utf-8 -*-
"""routes/install_routes.py - proverka/plan i zapusk ustanovki po zaprosu polzovatelya.

Ruchki:
  GET /install/check?app=chrome -> {ok, installed:bool}
  POST /install/plan {"app":"chrome"} -> {ok, plan:{...}}
  POST /install/run {"app":"chrome","source":"D:\\ChromeSetup.exe"} -> {ok}

Consens: domain "install.*" - dolzhen byt razreshen polzovatelem.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict
import os, platform, subprocess, shlex

from modules.ops.app_capabilities import is_installed, install_plan
from modules.thinking.intent_router import domain_needs_consent
from modules.thinking.consent_manager import set_rule
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("install_routes", __name__, url_prefix="/install")

def _is_windows() -> bool:
    return platform.system().lower().startswith("win")

@bp.route("/check", methods=["GET"])
def inst_check():
    app = (request.args.get("app") or "").strip().lower()
    if not app:
        return jsonify({"ok": False, "error": "app_required"}), 400
    return jsonify({"ok": True, "installed": is_installed(app)})

@bp.route("/plan", methods=["POST"])
def inst_plan():
    data = request.get_json(force=True, silent=True) or {}
    app = (data.get("app") or "").strip().lower()
    if not app:
        return jsonify({"ok": False, "error": "app_required"}), 400
    return jsonify({"ok": True, "plan": install_plan(app)})

@bp.route("/run", methods=["POST"])
def inst_run():
    data = request.get_json(force=True, silent=True) or {}
    app = (data.get("app") or "").strip().lower()
    src = (data.get("source") or "").strip()
    if not app or not src:
        return jsonify({"ok": False, "error": "app_and_source_required"}), 400
    domain = "install."+app
    if domain_needs_consent(domain):
        # We are waiting for explicit permission (you can do "ask_end" once)
        mode = (data.get("consent") or "").strip()  # allow/deny/ask_once
        if mode not in ("allow","ask_once"):
            return jsonify({"ok": False, "prompt": f"Razreshit ustanovku {app} iz {src}?", "domain": domain}), 403
        set_rule(domain, mode, persist=(mode!="ask_once"))

    if not os.path.exists(src):
        return jsonify({"ok": False, "error": "source_not_found"}), 400

    try:
        if _is_windows():
            # The silent key does not impose - it is unknown to each installer. Shows the normal installer.
            subprocess.Popen([src], shell=True)
        else:
            # If the file is .deb/.rpm - calls dpkg/rpm; if executable, run it; otherwise, we'll give you a hint
            if src.endswith(".deb"):
                subprocess.Popen(["/usr/bin/pkexec","/usr/bin/dpkg","-i",src])
            elif src.endswith(".rpm"):
                subprocess.Popen(["/usr/bin/pkexec","/usr/bin/rpm","-i",src])
            else:
                subprocess.Popen([src])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": f"exec_failed:{e}"}), 500


def register(app):
    app.register_blueprint(bp)
    return app