# -*- coding: utf-8 -*-
"""
tests/security/test_rbac_matrix_validate_yaml.py — minimalnaya validatsiya shtatnogo config/rbac_matrix.yaml.
"""
from __future__ import annotations

import os

import yaml  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_rbac_yaml_valid_and_nonempty():
    path_candidates = [
        os.path.join("config", "rbac_matrix.yaml"),
        os.path.join("config", "rbac_matrix.yml"),
    ]
    path = None
    for p in path_candidates:
        if os.path.exists(p):
            path = p
            break
    assert path is not None, "rbac_matrix.yaml not found"

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert isinstance(data, dict)
    assert "roles" in data and "rules" in data
    assert isinstance(data["roles"], dict)
    assert isinstance(data["rules"], dict)
    # Proverim, chto kritichnye klyuchi prisutstvuyut
    assert "/ops/*" in data["rules"] or "/ops" in data["rules"]
    assert "/ingest/*" in data["rules"] or "/ingest" in data["rules"]
# assert "/providers/select" in data["rules"]