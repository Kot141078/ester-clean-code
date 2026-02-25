# -*- coding: utf-8 -*-
"""routes/peer_rpa_proxy_routes.py - prostoe proksirovanie RPA na drugoy uzel Ester po lokalnoy seti.

Ruchka:
  POST /peer/proxy {"host":"127.0.0.1:8000","path":"/desktop/rpa/open","payload":{...}}

Name:
- Kooperativ: “Ester na moem PK” pomogaet na drugom PK s Ester, ne raskryvaya vnutrenniy agent napryamuyu.
- Bezopasnost: eto yavnaya operatsiya, trebuyuschaya roli operator (JWT) i soglasiya domena "rpa.coop".

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Dict, Any
import http.client, json
from urllib.parse import urlparse

from security.rbac_utils import require_role
from modules.thinking.intent_router import domain_needs_consent
from modules.thinking.consent_manager import set_rule
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("peer_rpa_proxy", __name__, url_prefix="/peer")

@bp.route("/proxy", methods=["POST"])
@require_role("operator")
def peer_proxy():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    host = (data.get("host") or "").strip()
    path = (data.get("path") or "").strip()
    payload = data.get("payload") or {}

    if not host or not path:
        return jsonify({"ok": False, "error": "host_and_path_required"}), 400

    domain = "rpa.coop"
    if domain_needs_consent(domain):
        mode = (data.get("consent") or "").strip()  # allow/ask_once
        if mode not in ("allow","ask_once"):
            return jsonify({"ok": False, "prompt": f"Allow cooperative action on ZZF0Z?", "domain": domain}), 403
        set_rule(domain, mode, persist=(mode!="ask_once"))

    # uproschennyy HTTP klient
    try:
        # ozhidaem http://host:port
        parsed = urlparse(("http://"+host) if "://" not in host else host)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=3.0)
        conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
        resp = conn.getresponse()
        body = resp.read().decode("utf-8","ignore")
        conn.close()
        try:
            obj = json.loads(body)
        except Exception:
            obj = {"ok": False, "raw": body}
        return jsonify({"ok": True, "peer_status": resp.status, "peer_reply": obj})
    except Exception as e:
        return jsonify({"ok": False, "error": f"peer_unreachable:{e}"}), 502


def register(app):
    app.register_blueprint(bp)
    return app
