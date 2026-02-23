# -*- coding: utf-8 -*-
"""
tests/security/test_rbac_matrix_loader.py — yunity dlya zagruzchika i matchinga RBAC-matritsy.
"""
from __future__ import annotations

import os
import textwrap

from security.rbac_matrix import check_access, load_matrix
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _write_tmp_matrix(tmp_path) -> str:
    data = textwrap.dedent(
        """
        roles:
          admin:
            allow: ["*"]
          ops:
            allow: ["/ops/*"]
          ingest:
            allow: ["/ingest/*"]
        rules:
          "/ops/*":
            require_any_role: ["admin", "ops"]
          "/ingest/*":
            require_any_role: ["admin", "ingest"]
          "/providers/select":
            require_any_role: ["admin", "provider_manager"]
        """
    ).strip()
    p = tmp_path / "rbac.yaml"
    p.write_text(data, encoding="utf-8")
    return str(p)


def test_load_and_check(tmp_path, monkeypatch):
    p = _write_tmp_matrix(tmp_path)
    monkeypatch.setenv("RBAC_MATRIX_PATH", p)

    m = load_matrix()
    assert "roles" in m and "rules" in m
    # admin vsegda mozhno
    assert check_access("/ops/restart", ["admin"], matrix=m) is True
    # ops imeet dostup k /ops/*
    assert check_access("/ops/rotate", ["ops"], matrix=m) is True
    # user — net
    assert check_access("/ops/rotate", ["user"], matrix=m) is False
    # ingest — tolko k /ingest/*
    assert check_access("/ingest/file", ["ingest"], matrix=m) is True
    assert check_access("/providers/select", ["provider_manager"], matrix=m) is True
    # put bez pravil — propuskaem (sovmestimost)
# assert check_access("/public/info", ["user"], matrix=m) is True