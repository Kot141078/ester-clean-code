# -*- coding: utf-8 -*-
"""routes/intent_routes.py - NL-intenty → vypolnenie (s soglasiyami) + UI-pult.

Ruchki:
  POST /intent/parse {"text":"..."} -> {ok, actions, need_install?}
  POST /intent/parse_run {"text":"..."} -> {ok, executed:[...], prompts?}
  GET /admin/intent (UI)

Performance:
- type="rpa", name="open" => POST /desktop/rpa/open
- type="macro", name="..." => POST /desktop/rpa/macro/run
- type="info" => vozvraschaetsya polzovatelyu kak podskazka

Consensus:
- Zaprashivaem soglasie po domain (for example, rpa.open, rpa.demo, rpa.coop, install.*)
- Esli soglasiya net - vozvraschaem {prompt:"razreshit?"}

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from typing import Any, Dict, List
import http.client, json

from modules.thinking.intent_router import parse, domain_needs_consent
from modules.thinking.consent_manager import set_rule
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("intent_routes", __name__, url_prefix="/intent")

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=3.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", "ignore")
    conn.close()
    try:
        return json.loads(data)
    except Exception:
        return {"ok": False, "error": "bad_reply", "raw": data}

@bp.route("/parse", methods=["POST"])
def intent_parse():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    res = parse(text)
    return jsonify(res)

@bp.route("/parse_run", methods=["POST"])
def intent_parse_run():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    consent_mode = (data.get("consent") or "").strip()  # 'allow'|'deny'|'ask'|'ask_once'
    res = parse(text)
    if not res.get("ok"):
        # vozmozhno need_install
        return jsonify(res), 200
    domain = res.get("domain") or "rpa.unknown"
    if domain_needs_consent(domain):
        if consent_mode in ("allow","deny","ask","ask_once"):
            # the user clearly answered - save
            set_rule(domain, consent_mode, persist=(consent_mode!="ask_once"))
            if consent_mode == "deny":
                return jsonify({"ok": False, "error": "denied", "domain": domain}), 403
        else:
            return jsonify({"ok": False, "prompt": f"Allow action in domain ZZF0Z?", "domain": domain})

    executed: List[Dict[str, Any]] = []
    for act in res.get("actions", []):
        if act["type"] == "rpa" and act["name"] == "open":
            executed.append({"act": act, "res": _post("/desktop/rpa/open", act["args"])})
        elif act["type"] == "macro":
            executed.append({"act": act, "res": _post("/desktop/rpa/macro/run", {"name": act["name"], "args": act.get("args", {})})})
        elif act["type"] == "info":
            executed.append({"act": act, "res": {"ok": True}})
        else:
            executed.append({"act": act, "res": {"ok": False, "error": "unknown_action"}})
    return jsonify({"ok": True, "executed": executed, "domain": domain})

@bp.route("/admin", methods=["GET"])
def intent_admin():
    return render_template("admin_intent.html")


def register(app):
    app.register_blueprint(bp)
    return app