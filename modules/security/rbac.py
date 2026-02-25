# -*- coding: utf-8 -*-
"""modules/security/rbac.py - gibridnyy RBAC: role po JWT/header, pravila po path/method, guard/dekorator, config iz file/env.

Mosty:
- Yavnyy: (JWT/Security ↔ Operatsii) kontrol dostupa bez sloma suschestvuyuschikh ruchek.
- Skrytyy #1: (Profile ↔ Audit) logiruem deny/allow/config dlya prozrachnosti.
- Skrytyy #2: (Policy ↔ Upravlenie) pravila/assign v JSON, s env-override i A/B.

Zemnoy abzats:
Kak strazh u vorot Ester: zritel smotrit, operator krutit ruchki, admin pravit mirom - a vse popytki fiksiruem, chtoby ne poteryat kontekst.

# c=a+b"""
from __future__ import annotations
import base64
import os, json, re, fnmatch, time, threading
from typing import Any, Dict, List, Set, Callable
from functools import wraps
from flask import request, jsonify  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MAP_FILE = os.getenv("RBAC_MAP", "data/security/rbac.json")
ENFORCE = bool(int(os.getenv("RBAC_ENFORCE", "0")))
AB = (os.getenv("RBAC_AB", "A") or "A").upper()

ROLES = ["viewer", "operator", "admin"]
ROLE_RANK = {r: i for i, r in enumerate(ROLES)}

_DEFAULT_RULES = {
    "/mem/alias": ["admin"],
    "/mem/compact": ["admin"],
    "/ingest/submit": ["operator", "admin"],
    "/cron/nightly/run": ["admin"],
}

_DEFAULT_ASSIGN = {"*": "viewer"}

_hits = {"allow": 0, "deny": 0, "last": 0}
_lock = threading.RLock()


def _b64url_decode_utf8(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        pad = "=" * ((4 - (len(raw) % 4)) % 4)
        payload = base64.urlsafe_b64decode((raw + pad).encode("ascii"))
        return payload.decode("utf-8", errors="strict")
    except Exception:
        return ""


def _header_utf8(name: str) -> str:
    base = str(name or "").strip()
    if not base:
        return ""
    b64 = request.headers.get(base + "-B64", "")
    text = _b64url_decode_utf8(b64)
    if text:
        return text
    return str(request.headers.get(base, "") or "")

def _passport(note: str, meta: Dict[str, Any]):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "sec://rbac")
    except Exception:
        pass

def _ensure():
    os.makedirs(os.path.dirname(MAP_FILE), exist_ok=True)
    if not os.path.isfile(MAP_FILE):
        json.dump({"rules": _DEFAULT_RULES, "assign": _DEFAULT_ASSIGN}, open(MAP_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load() -> Dict[str, Any]:
    with _lock:
        _ensure()
        try:
            d = json.load(open(MAP_FILE, "r", encoding="utf-8"))
        except Exception:
            d = {"rules": _DEFAULT_RULES, "assign": _DEFAULT_ASSIGN}
        # Env override for rules
        try:
            if os.getenv("RBAC_RULES_JSON"):
                d["rules"].update(json.loads(os.getenv("RBAC_RULES_JSON")))
        except Exception:
            pass
        return d

def _save(d: Dict[str, Any]):
    with _lock:
        json.dump(d, open(MAP_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _extract_role() -> str:
    # Iz JWT (role/roles, max po rank)
    try:
        from flask_jwt_extended import get_jwt  # type: ignore
        claims = get_jwt() or {}
        role = claims.get("role")
        if isinstance(role, str) and role in ROLES:
            return role
        roles = claims.get("roles") or []
        if roles:
            best = "viewer"
            for r in roles:
                if r in ROLES and ROLE_RANK[r] > ROLE_RANK[best]:
                    best = r
            return best
    except Exception:
        pass
    # Fallback: header X-User-Roles (comma sep)
    hdr = request.headers.get("X-User-Roles", "")
    if hdr:
        rset = {x.strip() for x in hdr.split(",") if x.strip() and x.strip() in ROLES}
        if rset:
            return max(rset, key=lambda r: ROLE_RANK[r])
    # Ili X-User + assign map
    user = _header_utf8("X-User") or "anon"
    assign = _load().get("assign", {})
    return assign.get(user, assign.get("*", "viewer"))

def _match_rule(path: str, method: str, rule: str) -> bool:
    # Format "METHNOD:pattern" (regex if ^$, otherwise glob)
    if ":" not in rule:
        return False
    m, pat = rule.split(":", 1)
    if m.upper() != method.upper():
        return False
    if pat.startswith("^") and pat.endswith("$"):
        return bool(re.match(pat, path))
    return fnmatch.fnmatch(path, pat)

def check(path: str, method: str, role: str) -> bool:
    if not ENFORCE:
        return True
    rules = _load().get("rules", {})
    need_roles = set()
    for pat, needs in rules.items():
        if _match_rule(path, method, pat):
            need_roles.update(needs)
    if not need_roles:
        return True  # Net pravila — allow
    allow = role in need_roles
    _hits["allow" if allow else "deny"] += 1
    _hits["last"] = int(time.time())
    return allow or AB == "B"  # Soft mode v B

def check_access(flask_request) -> Dict[str, Any]:
    role = _extract_role()
    path = flask_request.path
    method = flask_request.method.upper()
    allow = check(path, method, role)
    _passport("rbac_check", {"role": role, "path": path, "method": method, "allow": allow})
    return {"ok": True, "user": _header_utf8("X-User") or "anon", "role": role, "allow": allow}

def guard(app):
    @app.before_request
    def _rbac_guard():
        role = _extract_role()
        path = request.path
        method = request.method.upper()
        if not check(path, method, role):
            _passport("rbac_deny", {"role": role, "path": path, "method": method})
            return ("Forbidden (RBAC)", 403)

def require_role(min_role: str):
    def deco(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            role = _extract_role()
            if ROLE_RANK.get(role, 0) < ROLE_RANK.get(min_role, 0):
                _passport("rbac_deny", {"need": min_role, "have": role})
                return jsonify({"ok": False, "error": "forbidden", "need": min_role, "have": role}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco

def assign_user(user: str, role: str) -> Dict[str, Any]:
    if role not in ROLES:
        return {"ok": False, "error": "bad_role"}
    d = _load()
    d["assign"][user] = role
    _save(d)
    _passport("rbac_assign", {"user": user, "role": role})
    return {"ok": True, "user": user, "role": role}

def update_rules(new_rules: Dict[str, List[str]]) -> Dict[str, Any]:
    d = _load()
    d["rules"].update(new_rules)
    _save(d)
    _passport("rbac_config", {"rules": list(new_rules.keys())})
    return {"ok": True, "rules": d["rules"]}

def status() -> Dict[str, Any]:
    d = _load()
# return {"ok": True, "enforce": ENFORCE, "ab": AB, "roles": ROLES, "rules": d.get("rules", {}), "assign": d.get("assign", {}), "hits": dict(_hits)}
