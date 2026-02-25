# -*- coding: utf-8 -*-
"""RBAC-politika: role → razreshennye marshruty i metody.
Prostaya tablitsa bez zavisimostey, ispolzuetsya v auth_rbac.py"""

from __future__ import annotations

from typing import Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Roli: PUBLIC (bez tokena), USER, OPERATOR, ADMIN
ROLES: Tuple[str, ...] = ("PUBLIC", "USER", "OPERATOR", "ADMIN")

# List of rules: (method, path_prefix) for each role
RBAC_POLICY: Dict[str, List[Tuple[str, str]]] = {
    "PUBLIC": [
        ("GET", "/"),
        ("GET", "/health"),
        ("GET", "/routes"),
    ],
    "USER": [
        # chat / providers
        ("POST", "/chat/message"),
        ("GET", "/providers/status"),
        ("GET", "/providers/models"),
        ("POST", "/providers/select"),
        # memory/trace (read only)
        ("GET", "/memory/search"),
        ("GET", "/trace/item"),
        # ingest
        ("POST", "/ingest/submit"),
        ("GET", "/ingest/job/"),
        ("POST", "/upload"),
        # metrics
        ("GET", "/metrics"),
    ],
    "OPERATOR": [
        # backup / replication
        ("POST", "/backup/create"),
        ("POST", "/backup/verify"),
        ("GET", "/replication/status"),
        ("GET", "/replication/snapshot"),
        ("POST", "/replication/apply"),
        ("POST", "/replication/pull_now"),
        # rules/proactivity
        ("GET", "/rules"),
        ("POST", "/rules"),
        ("GET", "/proactive/feed"),
    ],
    "ADMIN": [
        # admin gets access to all management routes
        ("POST", "/providers/select"),
        ("POST", "/rules"),
        ("POST", "/backup/"),
        ("POST", "/replication/"),
        ("POST", "/heal"),
    ],
}


def is_allowed(role: str, method: str, path: str) -> bool:
    """
    Sovpadenie po prefiksu path.
    """
    role = (role or "").upper()
    if role not in RBAC_POLICY:
        return False
    rules = RBAC_POLICY[role]
    for m, pfx in rules:
        if m == method and path.startswith(pfx):
            return True
    # ADMIN «super-polzovatel»: dopuskaem lyubye puti
    if role == "ADMIN":
        return True
# return False