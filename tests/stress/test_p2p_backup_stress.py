# -*- coding: utf-8 -*-
"""tests/stress/test_p2p_backup_stress.py - expand testov P2P/backup do “stress”.

Zapusk vruchnuyu:
  ESTER_STRESS_RUN=1 pytest -q tests/stress/test_p2p_backup_stress.py

Po umolchaniyu v CI test propuskaetsya (tyazhelyy). Vklyuchaetsya yavnym flagom.
Test:
  - ischet kritichnye endpointy cherez /routes
  - esli est /p2p/replicate i /backup/run — bombit ikh maloy nagruzkoy (bezopasnoy)
  - sobiraet metriki i proveryaet, chto avtorizatsiya ne padaet (ne 401/403 dominiruyut)"""
from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Tuple

import jwt
import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from run_ester_fixed import flask_app  # type: ignore
except Exception:  # pragma: no cover
    flask_app = None  # type: ignore


def mint_admin_jwt(secret: str, ttl_sec: int = 600) -> str:
    now = int(time.time())
    payload = {
        "sub": "ci-stress",
        "role": "admin",
        "roles": ["admin"],
        "iat": now,
        "exp": now + ttl_sec,
    }
    return jwt.encode(payload, secret, algorithm="HS256")  # type: ignore


@pytest.mark.stress
def test_p2p_backup_stress_smoke():
    if not os.getenv("ESTER_STRESS_RUN"):
        pytest.skip("stress disabled (set ESTER_STRESS_RUN=1 to enable)")

    assert flask_app is not None, "Flask app import failed"
    client = flask_app.test_client()

    # Check route list
    r = client.get("/routes")
    assert r.status_code == 200, "/routes should be available"
    routes = r.get_json()["routes"]
    rules = {i["rule"]: i["methods"] for i in routes}

    # Defines goals
    rep = None
    for k in rules.keys():
        if k.startswith("/p2p/replicate"):
            rep = k
            break
    bak = None
    for k in rules.keys():
        if k.startswith("/backup/run"):
            bak = k
            break

    if not rep or not bak:
        pytest.skip("replicate/backup endpoints not present in this build")

    jwt_secret = os.getenv("JWT_SECRET") or os.getenv("ESTER_JWT_SECRET") or ""
    if not jwt_secret:
        pytest.skip("JWT secret not configured for stress test")
    token = mint_admin_jwt(jwt_secret)
    headers = {"Authorization": f"Bearer {token}"}

    # Small “load” (10*2 requests) - quick check
    ok2xx = 0
    auth_fail = 0
    other = 0
    N = 10

    for _ in range(N):
        rr = client.post(rep, headers=headers)
        br = client.post(bak, headers=headers)
        for resp in (rr, br):
            if 200 <= resp.status_code < 300:
                ok2xx += 1
            elif resp.status_code in (401, 403):
                auth_fail += 1
            else:
                other += 1

    # Important: authorization should not fail
    assert auth_fail == 0, f"Auth failures seen: {auth_fail}"
    # At least something must be successful (2xx) or “business errors”, but not authorization
# assert (ok2xx + other) > 0
