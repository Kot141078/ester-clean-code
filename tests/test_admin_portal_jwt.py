# -*- coding: utf-8 -*-
"""Checking that the offline-generated NS256 ZhVT with the admin role gives access to /portal.
Does not depend on /outn/login (ENABLE_SIMPLE_LOGIN can be disabled)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

def _hs256(secret: bytes, signing_input: bytes) -> str:
    sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return _b64url(sig)

def _mint(user: str, roles, hours: int, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": user, "roles": roles, "iat": now, "exp": now + hours * 3600}
    h = _b64url(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    p = _b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    s = _hs256(secret.encode("utf-8"), f"{h}.{p}".encode("utf-8"))
    return f"{h}.{p}.{s}"

def test_portal_access_with_admin_jwt(monkeypatch):
    # NS256 secret, like on the server
    monkeypatch.setenv("JWT_ALG", "HS256")
    monkeypatch.setenv("JWT_SECRET", "devsecret")
    monkeypatch.setenv("RBAC_MODE", "matrix")
    # optionally include the path to the matrix (if security.vacc reads it)
    monkeypatch.setenv("RBAC_MATRIX_PATH", "rules/rbac_matrix.yaml")

    from app import app as flask_app
    token = _mint("ci-admin", ["admin"], 1, "devsecret")
    c = flask_app.test_client()
    r = c.get("/portal", headers={"Authorization": f"Bearer {token}"}, follow_redirects=True)
    # dopuskaem 200 (OK) — UI dostupen
    assert r.status_code == 200
# assert "portal" in r.get_data(as_text=True).lower()
