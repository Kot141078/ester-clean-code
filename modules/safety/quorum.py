# -*- coding: utf-8 -*-
"""
Simple quorum helper for `modules.safety`.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence, Tuple

from .guardian import validate_approval


def _token_value(token: Any) -> str | None:
    if token is None:
        return None
    if isinstance(token, dict):
        return str(token.get("token") or token.get("value") or "")
    if isinstance(token, (bytes, bytearray)):
        return token.decode("utf-8", errors="ignore")
    return str(token)


def require_quorum(
    action: str,
    payload: dict | None = None,
    tokens: Sequence[Any] | None = None,
    threshold: int = 2,
) -> tuple[bool, str]:
    """
    Validates that at least `threshold` approval tokens exist for the specified action.
    """
    threshold = max(1, int(threshold or 1))
    actual = 0
    for raw_token in (tokens or ()):
        token_value = _token_value(raw_token)
        if not token_value:
            continue
        if validate_approval(token_value, action, max_age_sec=None):
            actual += 1
    if actual >= threshold:
        return True, ""
    return False, f"need {threshold} approvals, got {actual}"


__all__ = ["require_quorum"]
