# -*- coding: utf-8 -*-
"""
Shared outbound network guard (closed_box by default).

Rules:
- outbound internet is denied unless ESTER_ALLOW_OUTBOUND_NETWORK=1
- localhost loopback may be allowed via ESTER_ALLOW_LOCALHOST_NETWORK=1 (default: on)
"""
from __future__ import annotations

import ipaddress
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def allow_localhost() -> bool:
    return _truthy(os.getenv("ESTER_ALLOW_LOCALHOST_NETWORK", "1"))


def allow_outbound() -> bool:
    return _truthy(os.getenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0"))


def _is_loopback_host(host: str) -> bool:
    host = (host or "").strip().lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_local_url(url: str) -> bool:
    try:
        parsed = urlparse(str(url or ""))
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    return _is_loopback_host(parsed.hostname or "")


def allow_network(url: Optional[str] = None) -> bool:
    if allow_outbound():
        return True
    if url and is_local_url(url) and allow_localhost():
        return True
    return False


def deny_payload(url: str = "", target: str = "outbound_network") -> Dict[str, Any]:
    if url and is_local_url(url) and not allow_localhost():
        reason = "localhost_disabled"
        hint = "Set ESTER_ALLOW_LOCALHOST_NETWORK=1 for localhost traffic."
    else:
        reason = "closed_box_default_deny"
        hint = "Set ESTER_ALLOW_OUTBOUND_NETWORK=1 to allow outbound traffic."
    return {
        "ok": False,
        "error": "network_denied",
        "target": target,
        "url": str(url or ""),
        "reason": reason,
        "hint": hint,
    }


__all__ = [
    "allow_localhost",
    "allow_outbound",
    "is_local_url",
    "allow_network",
    "deny_payload",
]

