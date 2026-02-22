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
import logging
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from flask import Blueprint, g, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- Nastroyka blyuprinta ---
bp_caution_guard = Blueprint("caution_guard", __name__)

# --- Konfiguratsiya iz peremennykh okruzheniya ---
# Rezhim A/B: 'A' primenyaet pravila, 'B' tolko logiruet. Po umolchaniyu 'A'.
AB_MODE = (os.getenv("CAUTION_AB", "A") or "A").upper()
# Put k faylu s obedinennoy politikoy.
POLICY_FILE = os.getenv("APP_POLICY_MERGED", "data/policy/caution_rules.merged.json")
log = logging.getLogger(__name__)

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


def _truthy_env(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or default).strip().lower() in {"1", "true", "yes", "on", "y"}

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
