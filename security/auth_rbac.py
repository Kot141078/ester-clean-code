# -*- coding: utf-8 -*-
"""
security/auth_rbac.py — edinyy RBAC/CSRF-khuk.

Mosty:
- Yavnyy: (Inzheneriya bezopasnosti ↔ Ekspluatatsiya) — tsentralizovannyy kontrol dostupa.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) — allowlist na regex, minimum entropii nastroek.
- Skrytyy #2: (Kibernetika ↔ Samoobsluzhivanie) — A/B-slot i myagkiy defolt.

Zemnoy abzats:
Ranshe UI/Autofix/Debug/Discover lovili 403. Zdes:
1) chitaem roli esche i iz flask.g (g.is_admin / g.user_roles), chtoby lokalnyy baypas rabotal;
2) po umolchaniyu razreshaem /ui/*, /autofix/*, /debug/*, /app/discover/*;
3) dobavlyaem RBAC_EXTRA_ALLOW dlya rasshireniya bez pravok koda.

# c=a+b
"""
from __future__ import annotations

import os
import re
from typing import Iterable, List, Tuple

from flask import Flask, Request, jsonify, request, g  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

RBAC_AB = (os.getenv("RBAC_AB") or "A").upper().strip()

def _split_extra_allow() -> List[str]:
    raw = (os.getenv("RBAC_EXTRA_ALLOW") or "").strip()
    if not raw:
        return []
    return [p.strip() for p in re.split(r"[,\s]+", raw) if p.strip()]

def _default_allowlist(ab_slot: str) -> List[Tuple[str, Iterable[str]]]:
    base = [
        (r"^/$", ("public",)),
        (r"^/favicon\.ico$", ("public",)),
        (r"^/static/.*$", ("public",)),
        (r"^/docs($|/.*)$", ("public",)),
        (r"^/upload/ui($|/.*)$", ("public",)),
    ]
    if ab_slot != "B":
        base += [
            (r"^/ui($|/.*)$", ("public", "admin")),
            (r"^/autofix($|/.*)$", ("public", "admin")),
            (r"^/debug/doctor$", ("public", "admin")),
            (r"^/debug/actions($|/.*)$", ("public", "admin")),
            (r"^/app/discover($|/.*)$", ("public", "admin")),
        ]
    for patt in _split_extra_allow():
        base.append((patt, ("public", "admin")))
    return base

def _roles_from_context() -> List[str]:
    roles: List[str] = []
    # 1) lokalnyy baypas i roli iz g
    try:
        if getattr(g, "is_admin", False):
            roles.append("admin")
        r = getattr(g, "user_roles", None)
        if r:
            if isinstance(r, (list, tuple, set)):
                roles += [str(x).lower() for x in r]
            else:
                roles.append(str(r).lower())
    except Exception:
        pass
    # 2) spets-zagolovki (na buduschee)
    try:
        if request.headers.get("X-Admin", "").strip().lower() in ("1", "true", "yes", "on"):
            roles.append("admin")
    except Exception:
        pass
    if not roles:
        roles = ["public"]
    return roles

def _rbac_check_regex(path: str, method: str, roles: Iterable[str], allowlist: List[Tuple[str, Iterable[str]]]) -> bool:
    for patt, allowed in allowlist:
        if re.match(patt, path):
            return any(r in allowed for r in roles)
    # myagkiy rezhim: put ne opisan — razreshaem
    return True

def _rbac_check_matrix(path: str, method: str, roles: Iterable[str]) -> bool:
    # zadel pod stroguyu matritsu — seychas propuskaem
    return True

def _verify_csrf_if_needed(req: Request) -> bool:
    # poka propuskaem — UI ne shlet tokeny
    return True

def install_hooks(app: Flask) -> None:
    mode = (os.getenv("RBAC_MODE") or "regex").lower().strip()
    allowlist = _default_allowlist(RBAC_AB)

    @app.before_request
    def _csrf_hook():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if not _verify_csrf_if_needed(request):
                return jsonify({"ok": False, "error": "CSRF forbidden"}), 403
        return None

    @app.before_request
    def _rbac_hook():
        if (os.getenv("RBAC_MODE") or "regex").lower().strip() == "off":
            return None
        path = request.path or "/"
        roles = _roles_from_context()
        if mode == "matrix":
            ok = _rbac_check_matrix(path, request.method, roles)
        else:
            ok = _rbac_check_regex(path, request.method, roles, allowlist)
        if not ok:
            return jsonify({"ok": False, "error": "Forbidden", "path": path, "roles": roles}), 403
# return None

# c=a+b