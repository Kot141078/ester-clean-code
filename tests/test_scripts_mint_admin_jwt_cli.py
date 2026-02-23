# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import os
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _b64pad(s: str) -> bytes:
    # vosstanovim padding dlya dekodirovaniya
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def _hs256(secret: bytes, i: bytes) -> bytes:
    return hmac.new(secret, i, hashlib.sha256).digest()

def test_mint_function_generates_valid_hs256(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "devsecret")
    from scripts.mint_admin_jwt import mint  # type: ignore

    tok = mint("ci-admin", ["admin", "user"], 1)
    h, p, s = tok.split(".")
    header = json.loads(_b64pad(h))
    payload = json.loads(_b64pad(p))
    assert header["alg"] == "HS256" and header["typ"] == "JWT"
    assert "admin" in payload["roles"]
    assert payload["sub"] == "ci-admin"
    assert payload["exp"] > payload["iat"] and payload["exp"] - payload["iat"] <= 3600 + 5

    # verifikatsiya podpisi
    sig_ref = _hs256(b"devsecret", f"{h}.{p}".encode("utf-8"))
    assert base64.urlsafe_b64encode(sig_ref).decode("ascii").rstrip("=") == s