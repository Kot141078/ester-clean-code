# -*- coding: utf-8 -*-
"""middleware/caution_guard.py - Globalnyy okhrannik: chitaet politiku, otsenivaet risk zaprosa i trebuet soglasie (“pilyulyu”) dlya opasnykh operatsiy.

Mosty:
- Yavnyy: (Politika ↔ Ispolnenie) pravila iz JSON-fayla primenyayutsya ko vsem vkhodyaschim zaprosam, yavlyayas edinoy tochkoy kontrolya.
- Skrytyy #1: (Kibernetika ↔ Bezopasnost) A/B-slot pozvolyaet vklyuchat rezhim “tolko log” (B) bez realnykh blokirovok dlya bezopasnogo testirovaniya novykh pravil.
- Skrytyy #2: (Audit ↔ Prozrachnost) vse resheniya (proverka, blokirovka, razreshenie) pomechayutsya prichinami i vremenem v tsepochke sobytiy.
- Skrytyy #3: (Infoteoriya ↔ UX) pri blokirovke vozvraschaetsya detalnaya informatsiya o prichine i sposobe polucheniya razovogo tokena-soglasiya.

Zemnoy abzats:
Kak okhrana na vkhode: sveryaetsya so spiskom. Esli deystvie vyglyadit opasnym - prosit spetsialnyy propusk (“pilyulyu”) ili razvorachivaet, vezhlivo obyasnyaya prichinu.

# c=a+b"""
from __future__ import annotations
import json
import logging
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from flask import Blueprint, g, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- Nastroyka blueprinta ---
bp_caution_guard = Blueprint("caution_guard", __name__)

# --- Configuration from environment variables ---
# A/B mode: bAb applies the rules, bBb only logs. Default is bAb.
AB_MODE = (os.getenv("CAUTION_AB", "A") or "A").upper()
# Put k faylu s obedinennoy politikoy.
POLICY_FILE = os.getenv("APP_POLICY_MERGED", "data/policy/caution_rules.merged.json")
log = logging.getLogger(__name__)

# --- Optsionalnyy import moduley ---
try:
    # To verify the consent token (“pill”)
    from modules.ops.consent import verify as verify_consent_pill  # type: ignore
except ImportError:
    verify_consent_pill = None

try:
    # To add decisions to the audit chain
    from modules.policy.cautious_freedom import _append_chain as append_to_audit_chain  # type: ignore
except ImportError:
    append_to_audit_chain = None

# --- Osnovnaya logika ---

def _load_policy() -> Dict[str, Any]:
    """Zagruzhaet pravila politiki iz JSON-fayla."""
    try:
        with open(POLICY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # In case of error, returns an empty but valid policy structure
        return {"rules": []}

def _find_matching_rule(path: str, method: str, rules: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Finds the first rule matching the request path and method."""
    for rule in rules or []:
        if method != rule.get("method", "GET"):
            continue
        pattern = rule.get("pattern", "^$")
        try:
            if re.match(pattern, path):
                return rule
        except re.error:
            # Ignoriruem nevalidnye patterny v fayle politiki
            continue
    return None


def _truthy_env(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or default).strip().lower() in {"1", "true", "yes", "on", "y"}

@bp_caution_guard.before_app_request
def guard():
    """Eta funktsiya vypolnyaetsya pered kazhdym zaprosom.
    Ona proveryaet, sootvetstvuet li zapros riskovannoy operatsii, opisannoy v politike,
    i pri neobkhodimosti trebuet token-soglasie (“pilyulyu”)."""
    # 1. Skip the check for our own service routes
    if request.path.startswith("/caution/"):
        return None

    # 2. Load the policy and look for the corresponding rule
    policy = _load_policy()
    rule = _find_matching_rule(request.path or "", request.method or "GET", policy.get("rules"))

    # If the rule is not found or it does not require a “pill”, we do nothing.
    if not rule or not rule.get("requires_pill", False):
        return None

    # 3. The rule has been found, which means we need to check for the presence of a “pill”.
    token = request.headers.get("X-Pill") or request.args.get("pill") or ""
    
    # 4. Verify the “pill”
    is_ok = False
    detail = {}
    
    if not verify_consent_pill:
        is_ok, detail = False, {"error": "consent_module_unavailable"}
    else:
        try:
            is_ok, detail = verify_consent_pill(token, request.path or "", request.method or "GET")
        except Exception as e:
            is_ok, detail = False, {"error": f"consent_verification_failed:{e}"}

    # 5. Log the solution into the audit chain
    if append_to_audit_chain:
        audit_event = {
            "kind": "caution_guard_decision",
            "path": request.path,
            "method": request.method,
            "matched_rule": rule.get("pattern"),
            "decision": "allowed" if is_ok or AB_MODE == "B" else "blocked",
            "reason": "consent_pill_ok" if is_ok else ("ab_mode_B" if AB_MODE == "B" else "consent_pill_missing_or_invalid"),
            "detail": detail
        }
        append_to_audit_chain(audit_event)

    # 6. Apply blocking if necessary
    if is_ok or AB_MODE == "B":
        # We allow the request if the pill is valid or the non-blocking mode is enabled
        return None

    # Blocking the request
    response_payload = {
        "ok": False,
        "error": "consent_required",
        "rule": {
            k: rule[k] for k in ("pattern", "method", "risk", "level", "requires_pill") if k in rule
        },
        "hint": "POST /caution/pill/issue to get a one-time token; then pass ?pill=TOKEN or X-Pill header.",
        "detail": detail
    }
    
    resp = jsonify(response_payload)
    resp.status_code = 412  # Precondition Failed
    return resp

def register(app):
    """Registers a security guard's blueprint in the Flask application."""
    if getattr(app, "_caution_guard_registered", False):
        return app

    app.register_blueprint(bp_caution_guard)
    app._caution_guard_registered = True

    offline_default = "1" if not _truthy_env("ESTER_ALLOW_OUTBOUND_NETWORK", "0") else "0"
    enforce_offline = _truthy_env("ESTER_CAUTION_ENFORCE_OFFLINE", offline_default)
    blocked_prefixes = [
        p.strip()
        for p in (os.getenv("ESTER_CAUTION_BLOCKED_PREFIXES", "/oracle/,/providers/openai,/web/search,/comm/window/open") or "").split(",")
        if p.strip()
    ]

    @app.before_request
    def _caution_before_request():
        req_id = (request.headers.get("X-Request-Id") or "").strip() or str(uuid.uuid4())
        g.request_id = req_id
        g.caution_started_at = time.time()

        if enforce_offline:
            path = (request.path or "").lower()
            if any(path.startswith(p.lower()) for p in blocked_prefixes):
                payload = {
                    "ok": False,
                    "error": "offline_boundary",
                    "request_id": req_id,
                    "path": request.path,
                    "blocked_prefixes": blocked_prefixes,
                }
                resp = jsonify(payload)
                resp.status_code = 503
                return resp
        return None

    @app.after_request
    def _caution_after_request(resp):
        req_id = getattr(g, "request_id", "")
        if req_id and not resp.headers.get("X-Request-Id"):
            resp.headers["X-Request-Id"] = req_id
        resp.headers["X-Caution-Guard"] = "1"

        started = getattr(g, "caution_started_at", None)
        if started is not None:
            try:
                elapsed_ms = int((time.time() - float(started)) * 1000.0)
                resp.headers["X-Caution-Latency-Ms"] = str(max(0, elapsed_ms))
            except Exception:
                pass

        # Harden debug endpoints: normalize 5xx into JSON payload.
        if (request.path or "").startswith("/debug/") and int(resp.status_code or 0) >= 500:
            payload = {
                "ok": False,
                "error": "debug_endpoint_failed",
                "status": int(resp.status_code),
                "request_id": req_id,
                "path": request.path,
            }
            j = jsonify(payload)
            j.status_code = int(resp.status_code)
            if req_id:
                j.headers["X-Request-Id"] = req_id
            j.headers["X-Caution-Guard"] = "1"
            return j
        return resp

    log.info("caution_guard registered (offline=%s, blocked_prefixes=%s)", enforce_offline, blocked_prefixes)
    return app
