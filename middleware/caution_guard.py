# -*- coding: utf-8 -*-
"""
middleware/caution_guard.py — Globalnyy okhrannik: chitaet politiku, otsenivaet risk zaprosa i trebuet soglasie («pilyulyu») dlya opasnykh operatsiy.

Mosty:
- Yavnyy: (Politika ↔ Ispolnenie) pravila iz JSON-fayla primenyayutsya ko vsem vkhodyaschim zaprosam, yavlyayas edinoy tochkoy kontrolya.
- Skrytyy #1: (Kibernetika ↔ Bezopasnost) A/B-slot pozvolyaet vklyuchat rezhim «tolko log» (B) bez realnykh blokirovok dlya bezopasnogo testirovaniya novykh pravil.
- Skrytyy #2: (Audit ↔ Prozrachnost) vse resheniya (proverka, blokirovka, razreshenie) pomechayutsya prichinami i vremenem v tsepochke sobytiy.
- Skrytyy #3: (Infoteoriya ↔ UX) pri blokirovke vozvraschaetsya detalnaya informatsiya o prichine i sposobe polucheniya razovogo tokena-soglasiya.

Zemnoy abzats:
Kak okhrana na vkhode: sveryaetsya so spiskom. Esli deystvie vyglyadit opasnym — prosit spetsialnyy propusk («pilyulyu») ili razvorachivaet, vezhlivo obyasnyaya prichinu.

# c=a+b
"""
from __future__ import annotations
import json
import os
import re
from typing import Any, Dict, List, Optional

from flask import Blueprint, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- Nastroyka blyuprinta ---
bp_caution_guard = Blueprint("caution_guard", __name__)

# --- Konfiguratsiya iz peremennykh okruzheniya ---
# Rezhim A/B: 'A' primenyaet pravila, 'B' tolko logiruet. Po umolchaniyu 'A'.
AB_MODE = (os.getenv("CAUTION_AB", "A") or "A").upper()
# Put k faylu s obedinennoy politikoy.
POLICY_FILE = os.getenv("APP_POLICY_MERGED", "data/policy/caution_rules.merged.json")

# --- Optsionalnyy import moduley ---
try:
    # Dlya verifikatsii tokena-soglasiya («pilyuli»)
    from modules.ops.consent import verify as verify_consent_pill  # type: ignore
except ImportError:
    verify_consent_pill = None

try:
    # Dlya dobavleniya resheniy v tsepochku audita
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
        # V sluchae oshibki vozvraschaem pustuyu, no validnuyu strukturu politiki
        return {"rules": []}

def _find_matching_rule(path: str, method: str, rules: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Nakhodit pervoe pravilo, sootvetstvuyuschee puti i metodu zaprosa."""
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
    """
    Eta funktsiya vypolnyaetsya pered kazhdym zaprosom.
    Ona proveryaet, sootvetstvuet li zapros riskovannoy operatsii, opisannoy v politike,
    i pri neobkhodimosti trebuet token-soglasie («pilyulyu»).
    """
    # 1. Propuskaem proverku dlya sobstvennykh sluzhebnykh marshrutov
    if request.path.startswith("/caution/"):
        return None

    # 2. Zagruzhaem politiku i ischem sootvetstvuyuschee pravilo
    policy = _load_policy()
    rule = _find_matching_rule(request.path or "", request.method or "GET", policy.get("rules"))

    # Esli pravilo ne naydeno ili ono ne trebuet «pilyulyu», nichego ne delaem.
    if not rule or not rule.get("requires_pill", False):
        return None

    # 3. Pravilo naydeno, znachit, nuzhno proverit nalichie «pilyuli».
    token = request.headers.get("X-Pill") or request.args.get("pill") or ""
    
    # 4. Verifitsiruem «pilyulyu»
    is_ok = False
    detail = {}
    
    if not verify_consent_pill:
        is_ok, detail = False, {"error": "consent_module_unavailable"}
    else:
        try:
            is_ok, detail = verify_consent_pill(token, request.path or "", request.method or "GET")
        except Exception as e:
            is_ok, detail = False, {"error": f"consent_verification_failed:{e}"}

    # 5. Logiruem reshenie v tsepochku audita
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

    # 6. Primenyaem blokirovku, esli eto neobkhodimo
    if is_ok or AB_MODE == "B":
        # Razreshaem zapros, esli pilyulya validna ili vklyuchen neblokiruyuschiy rezhim 'B'
        return None

    # Blokiruem zapros
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
    """Registriruet blyuprint okhrannika v prilozhenii Flask."""
# app.register_blueprint(bp_caution_guard)
