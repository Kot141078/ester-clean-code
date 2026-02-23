# -*- coding: utf-8 -*-
"""
routes/nopush_guard_routes.py - HTTP-upravlenie lokalnym «stop-kranom» push cherez flag-fayl.

Endpointy:
  • GET  /admin/nopush/status  -> {"ok":true,"enabled":bool,"flag_path":".nopush","allow_env":0|1}
  • POST /admin/nopush/enable  -> sozdat .nopush (zapretit push po umolchaniyu)
  • POST /admin/nopush/disable -> udalit .nopush (snyat obschiy zapret; vse esche nuzhen ALLOW_PUSH=1 ili .allow_push)

# c=a+b
"""
from __future__ import annotations

import os
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_nopush = Blueprint("nopush_guard", __name__)

REPO_ROOT = os.getenv("REPO_ROOT", os.getcwd())
FLAG = os.path.join(REPO_ROOT, ".nopush")
ALLOW_FILE = os.path.join(REPO_ROOT, ".allow_push")


def register(app):  # pragma: no cover
    app.register_blueprint(bp_nopush)


def init_app(app):  # pragma: no cover
    app.register_blueprint(bp_nopush)


@bp_nopush.route("/admin/nopush/status", methods=["GET"])
def status():
    return jsonify(
        {
            "ok": True,
            "enabled": os.path.isfile(FLAG),
            "flag_path": FLAG,
            "allow_env": int(os.getenv("ALLOW_PUSH", "0")),
            "allow_file": int(os.path.isfile(ALLOW_FILE)),
        }
    )


@bp_nopush.route("/admin/nopush/enable", methods=["POST"])
def enable():
    try:
        # touch .nopush
        with open(FLAG, "a", encoding="utf-8"):
            pass
        return jsonify({"ok": True, "enabled": True, "flag_path": FLAG})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_nopush.route("/admin/nopush/disable", methods=["POST"])
def disable():
    try:
        if os.path.isfile(FLAG):
            os.remove(FLAG)
        return jsonify({"ok": True, "enabled": False, "flag_path": FLAG})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


__all__ = ["bp_nopush", "register", "init_app"]
# c=a+b