# -*- coding: utf-8 -*-
"""
modules/policy/network_policy.py

Single source of truth for outbound network policy.
No dependencies beyond stdlib/os.
"""
from __future__ import annotations

import os


DENY_CODE = "NET_OUTBOUND_DENIED"
ALLOW_CODE = "NET_OUTBOUND_ALLOWED"


def _truthy(v: str) -> bool:
    s = str(v or "").strip().lower()
    return s in ("1", "true", "yes", "on", "y")


def is_outbound_allowed():
    """
    Returns:
      (allowed: bool, reason: str, code: str)
    """
    if _truthy(os.getenv("CLOSED_BOX", "0")):
        return False, "closed_box", DENY_CODE

    mode = (os.getenv("WEB_FACTCHECK", "auto") or "auto").strip().lower()
    if mode == "never":
        return False, "web_factcheck_never", DENY_CODE

    # Optional explicit allowlist/search mode.
    if mode in ("search", "allowlist"):
        return True, "web_factcheck_search", ALLOW_CODE

    if mode in ("", "auto", "always", "on", "true", "1", "yes"):
        return True, "policy_allow", ALLOW_CODE

    # Unknown mode -> fail closed.
    return False, f"web_factcheck_unknown:{mode}", DENY_CODE

