# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Dict


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def is_outbound_network_allowed() -> bool:
    return _truthy(os.getenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0"))


def outbound_network_reason() -> str:
    if is_outbound_network_allowed():
        return "allowed_by_env"
    return "closed_box_default_deny"


def deny_payload(target: str = "outbound_network") -> Dict[str, str | bool]:
    return {
        "ok": False,
        "error": "network_denied",
        "target": str(target),
        "reason": outbound_network_reason(),
        "hint": "Set ESTER_ALLOW_OUTBOUND_NETWORK=1 to allow outbound network.",
    }


__all__ = [
    "is_outbound_network_allowed",
    "outbound_network_reason",
    "deny_payload",
]
