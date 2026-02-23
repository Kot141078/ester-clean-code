# -*- coding: utf-8 -*-
"""
tests/security/test_rbac_matrix_ci.py — proverka vklyucheniya i raboty RBAC-«matritsy».

Ideya:
  - /routes — nakhodim kritichnye ruchki (/ops/*, /providers/select, /ingest/*)
  - Bez tokena -> 401/403
  - Token s "user" -> 403
  - Token s "admin" -> NE 401/403 (dopuskaetsya 2xx/4xx v ramkakh biznes-logiki)

JWT: HS256, sekret beretsya iz ENV JWT_SECRET / ESTER_JWT_SECRET.
"""
from __future__ import annotations

import os
from typing import Dict, List

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from app import app as flask_app  # type: ignore
except Exception:  # pragma: no cover
    flask_app = None  # type: ignore


def _auth_token(client, role: str) -> str:
    r = client.post("/auth/login", json={"user": "ci-rbac", "role": role})
    assert r.status_code in (200, 201), f"/auth/login failed: {r.status_code}"
    data = r.get_json() or {}
    token = data.get("access_token")
    assert isinstance(token, str) and token, "access_token not returned"
    return token


def _find_target(routes: List[Dict], starts_with: str) -> str | None:
    for r in routes:
        if r["rule"].startswith(starts_with):
            return r["rule"]
    return None


@pytest.mark.parametrize(
    "prefix,needed_role",
    [
        ("/ops", "ops"),  # /ops/* — rol ops ili admin
        (
            "/providers/select",
            "provider_manager",
        ),  # /providers/select — rol provider_manager ili admin
        ("/ingest", "ingest"),  # /ingest/* — rol ingest ili admin
    ],
)
def test_rbac_matrix_on_critical(prefix: str, needed_role: str):
    assert flask_app is not None, "Flask app import failed"
    client = flask_app.test_client()

    # /routes
    rr = client.get("/routes")
    assert rr.status_code == 200, "/routes endpoint required"
    routes = rr.get_json()["routes"]

    target = _find_target(routes, prefix)
    if not target:
        pytest.skip(f"endpoint prefix {prefix} not present in this build")

    # 1) Bez tokena => 401/403
    resp = client.get(target)
    assert resp.status_code in (
        401,
        403,
    ), f"unauthorized access to {target} should be denied"

    # 2) user-token => 403
    user_tok = _auth_token(client, role="user")
    resp = client.get(target, headers={"Authorization": f"Bearer {user_tok}"})
    assert (
        resp.status_code == 403
    ), f"user role must be forbidden to {target}, got {resp.status_code}"

    # 3) admin-token => ne 401/403 (razreshen dostup na urovne RBAC)
    admin_tok = _auth_token(client, role="admin")
    resp = client.get(target, headers={"Authorization": f"Bearer {admin_tok}"})
    assert resp.status_code not in (
        401,
        403,
), f"admin should be allowed to {target}, got {resp.status_code}"
