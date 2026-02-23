# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import os
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _sign(secret: str, ts: int, method: str, path: str, body: bytes) -> str:
    msg = f"{ts}\n{method.upper()}\n{path}\n{_sha256(body)}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

def test_p2p_guard_401_without_headers(monkeypatch):
    monkeypatch.setenv("ESTER_P2P_SECRET", "s3cr3t")
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get("/p2p/echo")
    assert r.status_code == 401
    j = r.get_json()
    assert j and j.get("error") in {"p2p_signature_required", "p2p_bad_signature", "p2p_clock_skew"}

def test_p2p_guard_ok_with_signature(monkeypatch):
    monkeypatch.setenv("ESTER_P2P_SECRET", "s3cr3t")
    from app import app as flask_app
    c = flask_app.test_client()

    ts = int(time.time())
    path = "/p2p/echo"
    sig = _sign("s3cr3t", ts, "GET", path, b"")

    r = c.get(
        path,
        headers={
            "X-P2P-Ts": str(ts),
            "X-P2P-Node": "node-1",
            "X-P2P-Signature": sig,
        },
    )
    assert r.status_code == 200
    j = r.get_json()
    assert j and j.get("ok") is True

def test_p2p_guard_clock_skew(monkeypatch):
    monkeypatch.setenv("ESTER_P2P_SECRET", "s3cr3t")
    monkeypatch.setenv("ESTER_P2P_TS_WINDOW", "1")
    from app import app as flask_app
    c = flask_app.test_client()

    ts = int(time.time()) - 10
    path = "/p2p/echo"
    sig = _sign("s3cr3t", ts, "GET", path, b"")
    r = c.get(
        path,
        headers={
            "X-P2P-Ts": str(ts),
            "X-P2P-Node": "node-1",
            "X-P2P-Signature": sig,
        },
    )
    assert r.status_code == 401
    j = r.get_json()
    assert j and j.get("error") == "p2p_clock_skew"