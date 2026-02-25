# -*- coding: utf-8 -*-
"""security/rbac.py - prostoy matrichnyy RBAC-geyt s podderzhkoy ENV.
Drop-in sovmestimo s dampom po signature: attach_app(app).

ENV:
  RBAC_MODE: off | open | matrix (by default: matrix)
  RBAC_MATRIX: JSON {"role":[regex,...]} (esli ne zadano — defoltnaya matritsa nizhe)
  RBAC_LOG_DENY: 1/0 (logirovat otkazy v app.logger.warning)

Rules:
  • Roli berutsya iz JWT (claim roles/role). Esli JWT net - role guest.
  • Role guest vsegda dobavlyaetsya ko vsem zaprosam (bazovyy dostup).
  • Sovpadenie LYuBOGO patterna iz LYuBOY roli polzovatelya dostatochno dlya dopuska.
  • OPTIONS propuskaetsya vsegda.

Zemnoy abzats (inzheneriya):
Edinyy before_request-filtr s matritsey-regekspami minimiziruet stseplenie moduley.
Gost vidit tolko razreshennye publichnye stranitsy, operatsii zapisi - po JWT-rolyam.

Mosty:
- Yavnyy (Kibernetika ↔ Arkhitektura): odin regulyator dostupa na ves potok zaprosov.
- Skrytyy 1 (Infoteoriya ↔ Interfeysy): matritsa v ENV snizhaet entropiyu konfiguratsii.
- Skrytyy 2 (Anatomiya ↔ PO): kak bazovye i proizvolnye refleksy — guest i roli naslaivayutsya.

# c=a+b"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

from flask import abort, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Optional dependencies (soft)
try:
    from flask_jwt_extended import get_jwt, verify_jwt_in_request  # type: ignore
except Exception:  # pragma: no cover
    get_jwt = None  # type: ignore
    verify_jwt_in_request = None  # type: ignore

# ------------------------- helpers -------------------------


def _env_mode() -> str:
    m = (os.getenv("RBAC_MODE") or "matrix").strip().lower()
    return m if m in {"off", "open", "matrix"} else "matrix"


def _default_matrix() -> Dict[str, List[str]]:
    # Basic public access: health/indexes/docs/portal/static + UI authentication page and telegram panels
    return {
        "admin": [r".*"],
        "user": [r"^/(?!ops/|replication/).*$"],
        "guest": [
            r"^/(?:health|live|ready|routes|routes_index\.html|openapi\.json|docs|portal|$)",
            r"^/auth/auto(?:/.*)?$",
            r"^/auth/ui$",
            r"^/chat/telegram(?:/.*)?$",
            r"^/tg/ctrl/ui$",
            r"^/static/.*$",
            r"^/favicon\.ico$",
        ],
    }


def _load_matrix_from_env() -> Dict[str, List[str]]:
    raw = os.getenv("RBAC_MATRIX")
    if not raw:
        return _default_matrix()
    try:
        js = json.loads(raw)
        if not isinstance(js, dict):
            return _default_matrix()
        clean: Dict[str, List[str]] = {}
        for role, patterns in js.items():
            if not isinstance(role, str):
                continue
            if isinstance(patterns, list):
                clean[role] = [str(p) for p in patterns if isinstance(p, (str, bytes))]
        # garantiruem nalichie guest
        if "guest" not in clean:
            clean["guest"] = _default_matrix()["guest"]
        return clean or _default_matrix()
    except Exception:
        return _default_matrix()


def _compile_matrix(matrix: Dict[str, List[str]]):
    compiled: Dict[str, List[re.Pattern[str]]] = {}
    for role, pats in matrix.items():
        arr: List[re.Pattern[str]] = []
        for p in pats:
            try:
                arr.append(re.compile(p))
            except re.error:
                # propuskaem bitye patterny
                continue
        compiled[role] = arr
    return compiled


def _roles_from_request() -> List[str]:
    roles: List[str] = []
    # We are trying to extract the gastrointestinal tract if there is a library
    if verify_jwt_in_request and get_jwt:
        try:
            verify_jwt_in_request(optional=True)  # ne brosaem pri otsutstvii
            claims = get_jwt() or {}
            r = claims.get("roles") or claims.get("role") or []
            if isinstance(r, str):
                roles = [r]
            elif isinstance(r, list):
                roles = [str(x) for x in r]
        except Exception:
            roles = []
    # Bazovaya rol vsegda dostupna
    roles = [*(roles or []), "guest"]
    # Normalizuem registr
    roles = [r.lower() for r in roles]
    # Removing duplicates while maintaining order
    seen = set()
    ordered = []
    for r in roles:
        if r not in seen:
            ordered.append(r)
            seen.add(r)
    return ordered


# ------------------------- core -------------------------


def attach_app(app) -> None:
    """Connects the before_register filter. Idempotent: calling again does not add duplicates."""
    if getattr(app, "_rbac_attached", False):
        return
    app._rbac_attached = True  # type: ignore[attr-defined]

    mode = _env_mode()
    matrix = _load_matrix_from_env()
    compiled = _compile_matrix(matrix)
    log_deny = (os.getenv("RBAC_LOG_DENY") or "0").strip().lower() in {"1", "true", "yes"}

    # put it in the config for diagnostics/hot swap if desired
    app.config.setdefault("RBAC_MODE", mode)
    app.config.setdefault("RBAC_MATRIX", matrix)

    if mode in {"off", "open"}:
        # we do nothing - all requests pass
        return

    @app.before_request
    def _rbac_gate():
        # Razreshaem preflight
        if request.method == "OPTIONS":
            return None

        path = request.path or "/"
        roles = _roles_from_request()

        # Iteration by role: one match is enough
        allowed = False
        for role in roles:
            pats = compiled.get(role, [])
            for rx in pats:
                try:
                    if rx.search(path):
                        allowed = True
                        break
                except Exception:
                    continue
            if allowed:
                break

        if not allowed:
            if log_deny and getattr(app, "logger", None):
                try:
                    app.logger.warning(
                        "RBAC deny: path=%s roles=%s mode=%s",
                        path,
                        roles,
                        app.config.get("RBAC_MODE"),
                    )
                except Exception:
                    pass
            abort(403)

    # in case someone wants to check from outside
    app.extensions = getattr(app, "extensions", {})  # type: ignore[attr-defined]
# app.extensions["ester-rbac"] = {"mode": mode, "matrix": matrix}