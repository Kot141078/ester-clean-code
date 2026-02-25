# -*- coding: utf-8 -*-
"""modules/auth/rbac.py - obedinennyy RBAC: role iz JWT/headers/ENV, dinamicheskie pravila v JSON, guard i audit.

Mosty:
- Yavnyy: (Autentifikatsiya ↔ Avtorizatsiya) izvlekaet roli, proveryaet has_any_role dlya routov.
- Skrytyy #1: (Bezopasnost ↔ Prozrachnost) pravila v JSON, A/B, audit-log dostupov.
- Skrytyy #2: (Politika ↔ Rasshiryaemost) integratsiya s discover, extra-rules, validatsiya JWT.
- Skrytyy #3: (Memory ↔ Profile) logi v audit dlya BZ-sinkhronizatsii po P2P.

Zemnoy abzats:
Eto ne prosto turniket, a shveytsar s bloknotom: proverit beydzh (rol), propustit po pravilam, zapishet v zhurnal. Dlya Ester - zaschita ot fragmentatsii, s uvazheniem k ee rostu.

# c=a+b"""
from __future__ import annotations
import base64, hmac, hashlib, json, os, re, time
from typing import Any, Dict, Iterable, List, Set, Tuple
from flask import Blueprint, request, jsonify, g, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_rbac = Blueprint("rbac", __name__)

AB = (os.getenv("RBAC_AB", "A") or "A").upper()
RULES_PATH = os.getenv("RBAC_RULES", "data/policy/rbac_rules.json")
EXTRA_RULES_PATH = os.getenv("RBAC_EXTRA_RULES", "data/policy/extra_rbac.json")
AUDIT_LOG = os.getenv("RBAC_AUDIT_LOG", "data/policy/rbac_audit.log")
JWT_SECRET = os.getenv("JWT_SECRET", "").encode("utf-8")
REQUIRED = (os.getenv("RBAC_REQUIRED", "true").lower() == "true")
JWT_REQUIRED = (os.getenv("RBAC_JWT_REQUIRED", "true").lower() == "true")
DEV_ROLES = [x.strip().lower() for x in (os.getenv("RBAC_DEV_ROLES", "admin,operator,viewer") or "").split(",") if x.strip()]
ROLES_LEVEL = {"viewer": 1, "operator": 5, "admin": 10}
HDR_ROLES = os.getenv("RBAC_HEADER_ROLES", "X-User-Roles")
_LAB_WARNED = False


def _lab_mode_enabled() -> bool:
    v = str(os.getenv("ESTER_LAB_MODE", "0") or "").strip().lower()
    return v in ("1", "true", "yes", "on", "y")

def _ensure():
    os.makedirs(os.path.dirname(RULES_PATH), exist_ok=True)
    if not os.path.isfile(RULES_PATH):
        json.dump({
            "rules": [
                {"pattern": "^/mem/alias$", "method": "POST", "min_role": "operator"},
                {"pattern": "^/mem/compact$", "method": "POST", "min_role": "admin"},
                {"pattern": "^/ingest/submit$", "method": "POST", "min_role": "operator"}
            ]
        }, open(RULES_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if not os.path.isfile(EXTRA_RULES_PATH):
        json.dump({"rules": []}, open(EXTRA_RULES_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)

def _load_rules() -> Dict[str, Any]:
    _ensure()
    rules = json.load(open(RULES_PATH, "r", encoding="utf-8"))
    # Merge with extra (extension)
    try:
        extra = json.load(open(EXTRA_RULES_PATH, "r", encoding="utf-8")).get("rules", [])
        existing_patterns = {r["pattern"] for r in rules.get("rules", [])}
        for er in extra:
            if er.get("pattern") not in existing_patterns:
                rules["rules"].append(er)
        _save_rules(rules)
    except Exception:
        pass
    return rules

def _save_rules(j: Dict[str, Any]):
    json.dump(j, open(RULES_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _log_audit(msg: str):
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {request.remote_addr or 'unknown'} {msg}\n")


def _warn_lab_mode_once() -> None:
    global _LAB_WARNED
    if _LAB_WARNED:
        return
    _LAB_WARNED = True
    try:
        current_app.logger.warning("RBAC LAB MODE ENABLED")
    except Exception:
        pass
    try:
        _log_audit("RBAC LAB MODE ENABLED (DEV_ROLES fallback active)")
    except Exception:
        pass

def _b64url_dec(s: str) -> bytes:
    s = s.strip().replace("-", "+").replace("_", "/")
    q = len(s) % 4
    if q: s += "=" * (4 - q)
    return base64.b64decode(s)

def _jwt_parse(token: str) -> Tuple[Dict[str, Any], Dict[str, Any], bytes]:
    parts = token.split(".")
    if len(parts) != 3: return {}, {}, b""
    try:
        header = json.loads(_b64url_dec(parts[0]).decode("utf-8"))
        payload = json.loads(_b64url_dec(parts[1]).decode("utf-8"))
        sig = _b64url_dec(parts[2])
        return header, payload, sig
    except Exception:
        return {}, {}, b""

def _jwt_verify_hs256(token: str) -> bool:
    if not JWT_REQUIRED:
        return True
    parts = token.split(".")
    if len(parts) != 3:
        return False
    signing = f"{parts[0]}.{parts[1]}".encode("utf-8")
    given = _b64url_dec(parts[2])
    secrets: List[bytes] = []
    cfg_secret = current_app.config.get("JWT_SECRET_KEY")
    if isinstance(cfg_secret, str) and cfg_secret:
        secrets.append(cfg_secret.encode("utf-8"))
    if JWT_SECRET:
        secrets.append(JWT_SECRET)
    env_secret = os.getenv("JWT_SECRET_KEY", "")
    if env_secret:
        secrets.append(env_secret.encode("utf-8"))
    # Compatibility: if the secret is not specified, leave the soft mode.
    if not secrets:
        return True
    for sec in secrets:
        expected = hmac.new(sec, signing, hashlib.sha256).digest()
        if hmac.compare_digest(expected, given):
            return True
    return False


def _verified_claims_from_flask_jwt() -> Dict[str, Any]:
    try:
        from flask_jwt_extended import get_jwt, verify_jwt_in_request  # type: ignore

        verify_jwt_in_request(optional=True)
        claims = get_jwt()
        return claims if isinstance(claims, dict) else {}
    except Exception:
        return {}

def _roles_from_payload(p: Dict[str, Any]) -> Set[str]:
    xs = set()

    def _collect(obj: Any) -> None:
        if not isinstance(obj, dict):
            return
        if isinstance(obj.get("roles"), list):
            xs.update([str(x).lower() for x in obj["roles"]])
        if isinstance(obj.get("role"), str):
            xs.add(obj["role"].lower())
        if isinstance(obj.get("scope"), str):
            xs.update([t.strip().lower() for t in obj["scope"].split() if t.strip()])
        if isinstance(obj.get("permissions"), list):
            xs.update([str(x).lower() for x in obj["permissions"]])

    _collect(p)
    _collect(p.get("sub"))
    _collect(p.get("identity"))
    _collect(p.get("user"))
    return xs

def _get_auth_token() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "): return auth.split(" ", 1)[1].strip()
    return ""

def get_current_roles() -> List[str]:
    roles: Set[str] = set()
    # 0) Contextual roles from other guard layers (if any)
    g_roles = getattr(g, "user_roles", None)
    if isinstance(g_roles, (list, tuple, set)):
        roles.update([str(x).strip().lower() for x in g_roles if str(x).strip()])
    # 1) Iz headers (X-User-Roles ili X-Roles)
    hdr = request.headers.get(HDR_ROLES, "") or request.headers.get("X-Roles", "")
    if hdr:
        roles.update([x.strip().lower() for x in hdr.split(",") if x.strip()])
    # 2) From ZhVT (via flask_zhvt_extended: already verified slimes)
    claims = _verified_claims_from_flask_jwt()
    if claims:
        roles.update(_roles_from_payload(claims))
    # 3) Falbatsk: manual disassembly of ZhVT Bearer (for Legacy/outside ZhVT_reguired)
    tok = _get_auth_token()
    if tok:
        try:
            if _jwt_verify_hs256(tok):
                _, pl, _ = _jwt_parse(tok)
                roles.update(_roles_from_payload(pl))
        except Exception:
            pass
    # 4) Fallback ENV/DEV
    if not roles and _lab_mode_enabled() and DEV_ROLES:
        _warn_lab_mode_once()
        roles.update(DEV_ROLES)
    # Save in g for reuse
    g.rbac_roles = sorted(list(roles))  # type: ignore
    return g.rbac_roles  # type: ignore

user_roles = get_current_roles  # Synonym for compatibility

def has_any_role(required: Iterable[str]) -> bool:
    if not REQUIRED: return True
    need = set([str(x).lower() for x in required or []])
    if not need: return True
    got = set(get_current_roles())
    if not got:
        try:
            _log_audit(f"Denied role-check: {request.path} {request.method} reason=no_roles need={sorted(list(need))}")
        except Exception:
            pass
        return False
    return bool(got & need)

def _jwt_role_level() -> int:
    roles = get_current_roles()
    if not roles:
        return 0
    return max(ROLES_LEVEL.get(r, 1) for r in roles)

def _allowed_by_rules() -> Tuple[bool, str]:
    path = request.path or ""
    method = request.method or "GET"
    r = _load_rules()
    need_level = 0
    protected = False
    min_role_name = "viewer"
    for rule in r.get("rules", []):
        if method != rule.get("method", "GET"): continue
        if re.match(rule.get("pattern", "^$"), path):
            protected = True
            min_role = str(rule.get("min_role", "viewer") or "viewer").lower()
            lvl = ROLES_LEVEL.get(min_role, 1)
            if lvl >= need_level:
                need_level = lvl
                min_role_name = min_role
    if not protected:
        return True, "unprotected"
    roles = get_current_roles()
    if not roles:
        return False, f"no_roles_for_protected need={min_role_name}"
    if _jwt_role_level() < need_level:
        return False, f"insufficient_role need={min_role_name} got={roles}"
    return True, f"matched need={min_role_name}"

@bp_rbac.before_app_request
def guard():
    if request.path.startswith("/rbac/"): return None
    allowed, reason = _allowed_by_rules()
    if not allowed:
        _log_audit(f"Denied: {request.path} {request.method} role={get_current_roles()} reason={reason}")
        return jsonify({"ok": False, "error": "rbac_forbidden"}), 403
    _log_audit(f"Allowed: {request.path} {request.method} role={get_current_roles()} reason={reason}")
    return None

@bp_rbac.route("/rbac/status", methods=["GET"])
def status():
    return jsonify({"ok": True, "ab": AB, "roles": get_current_roles(), **_load_rules()})

@bp_rbac.route("/rbac/set", methods=["POST"])
def set_rules():
    if not has_any_role(["admin"]):
        return jsonify({"ok": False, "error": "rbac_forbidden"}), 403
    d = request.get_json(True, True) or {}
    rules = d.get("rules")
    if not isinstance(rules, list):
        return jsonify({"ok": False, "error": "rules_required"}), 400
    j = {"rules": rules}
    _save_rules(j)
    _log_audit(f"Rules updated by {get_current_roles()}")
    return jsonify({"ok": True, **j})

@bp_rbac.route("/rbac/audit", methods=["GET"])
def audit():
    if not has_any_role(["admin"]):
        return jsonify({"ok": False, "error": "rbac_forbidden"}), 403
    try:
        with open(AUDIT_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()[-50:]  # Last 50 for short
        return jsonify({"ok": True, "audit": lines})
    except Exception:
        return jsonify({"ok": False, "error": "audit_read_failed"})

def register(app):
    app.register_blueprint(bp_rbac)
    return app
