# -*- coding: utf-8 -*-
"""security/rbac_matrix.py - RBAC "matritsa": zagruzka, proverka dostupa, optsionalnyy before_request-khuk.

Name:
- load_matrix(path=ENV RBAC_MATRIX_PATH | config/rbac_matrix.yaml) -> dict
- check_access(path:str, roles:list[str], method:str|None, matrix:dict|None) -> bool
- register_rbac_matrix(app, path=None, extractor=None) -> None
  Podklyuchaet myagkiy before_request-khuk, kotoryy:
    • chitaet roli iz extractor(request) ili iz flask.g.user_roles / g.jwt (roles)
    • dlya admin — polnyy dostup
    • dlya putey iz rules — trebuet odnu iz roley iz require_any_role
    • na nepropisannye puti - propuskaet (ne lomaem suschestvuyuschie politiki)

Sovmestimost:
- Nothing ne menyaet avtomaticheski. Vyzyvaetsya tolko esli app.py uzhe ispolzuet etot modul.
- Esli JWT uzhe proveryaetsya globalno, my lish uvazhaem roles iz g."""
from __future__ import annotations

import fnmatch
import os
from typing import Any, Dict, List, Optional, Tuple

import yaml  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from flask import g, jsonify, request  # type: ignore
except Exception:  # pragma: no cover
    g = None  # type: ignore

_DEFAULT_PATHS = [
    os.path.join("config", "rbac_matrix.yaml"),
    os.path.join("config", "rbac_matrix.yml"),
]


def _matrix_path() -> str:
    p = os.getenv("RBAC_MATRIX_PATH")
    if p and os.path.exists(p):
        return p
    for c in _DEFAULT_PATHS:
        if os.path.exists(c):
            return c
    return _DEFAULT_PATHS[0]


def load_matrix(path: Optional[str] = None) -> Dict[str, Any]:
    path = path or _matrix_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return {"roles": {}, "rules": {}}
        data.setdefault("roles", {})
        data.setdefault("rules", {})
        return data
    except Exception:
        return {"roles": {}, "rules": {}}


def _normalize_roles(roles: Any) -> List[str]:
    if roles is None:
        return []
    if isinstance(roles, str):
        return [roles]
    if isinstance(roles, (list, tuple, set)):
        return [str(r) for r in roles]
    return []


def _match_rule(path: str, rules: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Returns the first matching entry (pattern, rule).
    Priority is the order of announcement in YML (dist while maintaining the order in Pos. 7+)."""
    for patt, rule in rules.items():
        if fnmatch.fnmatch(path, patt):
            return patt, (rule or {})
    return None


def check_access(
    path: str,
    roles: List[str],
    method: Optional[str] = None,
    matrix: Optional[Dict[str, Any]] = None,
) -> bool:
    """Vozvraschaet True, esli dostup razreshen matritsey, inache False.
    Rules:
      - Esli est rol admin -> True
      - Esli po path naydeno pravilo rules[pattern].require_any_role -> nuzhna khotya by odna rol polzovatelyu
      - Esli pravilo ne naydeno -> propuskaem (True), chtoby ne lomat staruyu politiku
    Primechanie: Metod (GET/POST...) poka ne uchityvaem (mozhno rasshirit v buduschem)."""
    roles = _normalize_roles(roles)
    if "admin" in roles:
        return True

    m = matrix or load_matrix()
    rule_hit = _match_rule(path, m.get("rules", {}))
    if rule_hit is None:
        return True  # no explicit rule -> allow

    _, rule = rule_hit
    need = _normalize_roles(rule.get("require_any_role"))
    if not need:
        return True  # no explicit requirement
    return any(r in roles for r in need)


# ---------------- before_request-khuk (optsionalno) ----------------


def _extract_roles_default(req) -> List[str]:
    """Izvlekaet roli iz flask.g, ne trogaya JWT parsing (kotoryy uzhe est v prilozhenii).
    Priority:
      1) g.user_roles
      2) g.jwt['roles']
      3) g.jwt['role']
      4) empty"""
    try:
        if hasattr(g, "user_roles") and g.user_roles:
            return _normalize_roles(getattr(g, "user_roles"))
        if hasattr(g, "jwt") and isinstance(getattr(g, "jwt"), dict):
            j = getattr(g, "jwt")
            if isinstance(j.get("roles"), (list, tuple, set, str)):
                return _normalize_roles(j.get("roles"))
            if j.get("role"):
                return _normalize_roles(j.get("role"))
    except Exception:
        pass
    return []


def register_rbac_matrix(app, path: Optional[str] = None, extractor=None):
    """Podklyuchaet myagkiy RBAC-khuk. Vyzyvat iz app.py (esli trebuetsya).
    Primer:
        from security.rbac_matrix import register_rbac_matrix
        register_rbac_matrix(app)"""
    mat = load_matrix(path)
    _extract = extractor or _extract_roles_default

    @app.before_request  # type: ignore[attr-defined]
    def _rbac_matrix_guard():
        try:
            p = request.path  # type: ignore
        except Exception:
            return None
        roles = _extract(request)
        allowed = check_access(p, roles, method=getattr(request, "method", None), matrix=mat)
        if not allowed:
            # We return 403 without changing the rest of the application logic.
            return (
                jsonify({"ok": False, "error": "forbidden_by_rbac_matrix", "path": p}),
                403,
            )
# return None