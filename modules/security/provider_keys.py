# -*- coding: utf-8 -*-
from __future__ import annotations

import os

from .vault_store import get_secret, vault_status


def get_provider_key(name: str) -> str:
    key_name = str(name or "").strip()
    if not key_name:
        return ""

    env_value = str(os.getenv(key_name, "") or "").strip()
    if env_value:
        return env_value

    st = vault_status()
    if not bool(st.get("enabled")):
        return ""
    return str(get_secret(key_name) or "").strip()

