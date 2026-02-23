# -*- coding: utf-8 -*-
"""
routes/routes_rules.py - REST API dlya raboty s YAML-pravilami avtomatizatsiy.

Endpointy (JWT):
  GET  /rules/config            - otdat tekuschiy bundle (s putem fayla)
  POST /rules/install_triggers  - ustanovit vse triggery v planirovschik
  POST /rules/run               - vypolnit avtomatizatsiyu po id (ruchnoy zapusk)
  POST /rules/run_due           - zapustit planirovschik (prinuditelno «seychas»)

Registratsiya:
  from routes.routes_rules import register_rules_routes
  register_rules_routes(app, url_prefix="/rules")

Mosty:
- Yavnyy: (Planirovschik ↔ Logika) tsentralizovannyy REST dlya ustanovki/zapuska pravil.
- Skrytyy #1: (Prozrachnost ↔ Audit) determinirovannye JSON-otvety - legko logirovat v «profile».
- Skrytyy #2: (Infoteoriya ↔ Shum) tochechnye vyzovy run/run_due snizhayut izbytochnyy fon sobytiy.

Zemnoy abzats:
Eto «pult upravleniya» avtomatizatsiyami: posmotret konfig, postavit triggery, vruchnuyu dernut
pravilo ili skazat planirovschiku «pora». Nikakoy magii - tolko chetkie knopki.

# c=a+b
"""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore

from modules.scheduler_engine import run_due
from rule_engine import install_automation_triggers, load_rules, run_automation
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def register_rules_routes(app, url_prefix: str = "/rules"):
    @app.get(f"{url_prefix}/config")
    @jwt_required()
    def rules_config():
        try:
            bundle = load_rules()
            return jsonify(
                {
                    "ok": True,
                    "version": getattr(bundle, "version", None),
                    "defaults": getattr(bundle, "defaults", {}),
                    "sources": getattr(bundle, "sources", {}),
                    "pipes": getattr(bundle, "pipes", {}),
                    "conditions": getattr(bundle, "conditions", {}),
                    "automations": getattr(bundle, "automations", {}),
                }
            )
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post(f"{url_prefix}/install_triggers")
    @jwt_required()
    def rules_install_triggers():
        try:
            bundle = load_rules()
            res = install_automation_triggers(bundle)
            return jsonify(res if isinstance(res, dict) else {"ok": True, "result": res})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post(f"{url_prefix}/run")
    @jwt_required()
    def rules_run():
        data = request.get_json(silent=True) or {}
        automation_id = (data.get("automation_id") or data.get("id") or "").strip()
        if not automation_id:
            return jsonify({"ok": False, "error": "automation_id required"}), 400
        try:
            bundle = load_rules()
            res = run_automation(bundle, automation_id)
            return jsonify(res if isinstance(res, dict) else {"ok": True, "result": res})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post(f"{url_prefix}/run_due")
    @jwt_required()
    def rules_run_due():
        data = request.get_json(silent=True) or {}
        now_ts = data.get("now_ts")
        try:
            ts = float(now_ts) if now_ts is not None else None
        except Exception:
            ts = None
        try:
            res = run_due(now_ts=ts)
            return jsonify(res if isinstance(res, dict) else {"ok": True, "result": res})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500


__all__ = ["register_rules_routes"]
# c=a+b


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
def register(app):
    # vyzyvaem suschestvuyuschiy register_rules_routes(app) (url_prefix beretsya po umolchaniyu vnutri funktsii)
    return register_rules_routes(app)

# === /AUTOSHIM ===