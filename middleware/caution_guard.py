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
import os
import re
from typing import Any, Dict, List, Optional

from flask import Blueprint, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- Nastroyka blueprinta ---
bp_caution_guard = Blueprint("caution_guard", __name__)

# --- Configuration from environment variables ---
# A/B mode: bAb applies the rules, bBb only logs. Default is bAb.
AB_MODE = (os.getenv("CAUTION_AB", "A") or "A").upper()
# Put k faylu s obedinennoy politikoy.
POLICY_FILE = os.getenv("APP_POLICY_MERGED", "data/policy/caution_rules.merged.json")

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
# app.register_blueprint(bp_caution_guard)
