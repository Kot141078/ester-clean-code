# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Iterable, Tuple

_TRUE_VALUES = {"1", "true", "yes", "on", "y"}


def parse_bool_env(name: str, default: bool = False) -> bool:
    raw_default = "1" if bool(default) else "0"
    raw = str(os.getenv(name, raw_default) or raw_default).strip().lower()
    return raw in _TRUE_VALUES


def require_env_exact(name: str, expected: str) -> Tuple[bool, str]:
    actual = str(os.getenv(name, "") or "").strip()
    return (actual == str(expected), actual)


def explain_missing_prereq(items: Iterable[str]) -> str:
    missing = [str(item).strip() for item in items if str(item).strip()]
    if not missing:
        return ""
    return "missing_prereqs: " + ", ".join(missing)


def witness_ready() -> bool:
    if parse_bool_env("ESTER_L4W_WITNESS", False):
        return True
    try:
        from modules.runtime import l4w_witness  # type: ignore

        probe = getattr(l4w_witness, "is_enabled", None)
        if callable(probe):
            return bool(probe())
    except Exception:
        pass
    return False
