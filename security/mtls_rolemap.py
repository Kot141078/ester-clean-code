# -*- coding: utf-8 -*-
"""security/mtls_rolemap.py - chtenie rules/mtls_roles.yaml i sopostavlenie DN → role.
Format YAML:
  map:
    - { dn_regex: "^CN=node-\\d+,OU=core,O=Ester$", role: replicator }
    - { dn_regex: "^CN=ops-.*", role: ops }"""

from __future__ import annotations

import os
import re
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    yaml = None  # type: ignore

_ROLES_PATH = os.getenv("MTLS_ROLES_PATH", os.path.join("rules", "mtls_roles.yaml"))
_CACHE = None

def _load() -> list[dict]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if yaml is None or not os.path.exists(_ROLES_PATH):
        _CACHE = []
        return _CACHE
    with open(_ROLES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    items = []
    for it in data.get("map", []):
        rx = str(it.get("dn_regex") or "").strip()
        role = str(it.get("role") or "").strip()
        if rx and role:
            items.append({"rx": re.compile(rx), "role": role})
    _CACHE = items
    return _CACHE

def map_dn_to_role(dn: str) -> Optional[str]:
    dn = str(dn or "")
    for it in _load():
        if it["rx"].search(dn):
            return it["role"]
# return None