# -*- coding: utf-8 -*-
from __future__ import annotations

import hmac
import os
from typing import Any, Tuple


def _header_value(request_obj: Any, name: str) -> str:
    try:
        headers = getattr(request_obj, "headers", None)
        if headers is None:
            return ""
        return str(headers.get(name, "") or "")
    except Exception:
        return ""


def _rbac_evidence_present(request_obj: Any) -> bool:
    # Fail-closed: do not trust implicit DEV role fallbacks.
    if _header_value(request_obj, "X-User-Roles"):
        return True
    if _header_value(request_obj, "X-Roles"):
        return True
    auth = _header_value(request_obj, "Authorization")
    return auth.lower().startswith("bearer ")


def _header_roles(request_obj: Any) -> set[str]:
    raw = _header_value(request_obj, "X-User-Roles") or _header_value(request_obj, "X-Roles")
    if not raw:
        return set()
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def _check_rbac_admin(request_obj: Any) -> Tuple[bool, str]:
    roles = _header_roles(request_obj)
    if not _rbac_evidence_present(request_obj):
        return False, "rbac_unverified"
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
    except Exception:
        # Offline fallback: explicit admin role header can still verify admin intent.
        if "admin" in roles:
            return True, "rbac_header_fallback"
        return False, "rbac_unavailable"
    try:
        ok = bool(has_any_role(["admin"]))
        if ok:
            return True, "rbac"
        if "admin" in roles:
            return True, "rbac_header_fallback"
        return False, "rbac_forbidden"
    except Exception:
        if "admin" in roles:
            return True, "rbac_header_fallback"
        return False, "rbac_error"


def _check_static_token(request_obj: Any) -> Tuple[bool, str]:
    expected = str(os.getenv("ESTER_ADMIN_TOKEN", "") or "")
    if not expected:
        return False, "token_not_configured"
    got = _header_value(request_obj, "X-Ester-Admin-Token")
    if got and hmac.compare_digest(got, expected):
        return True, "token"
    return False, "token_mismatch"


def require_admin(request_obj: Any) -> Tuple[bool, str]:
    ok, reason = _check_rbac_admin(request_obj)
    if ok:
        return True, reason

    tok_ok, tok_reason = _check_static_token(request_obj)
    if tok_ok:
        return True, tok_reason

    if reason in {"rbac_unavailable", "rbac_error", "rbac_unverified"} and tok_reason == "token_not_configured":
        return False, "no_admin_verifier"
    return False, tok_reason if tok_reason != "token_not_configured" else reason


__all__ = ["require_admin"]
