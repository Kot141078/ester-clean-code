# -*- coding: utf-8 -*-
"""
tests/security/test_p2p_security.py — klyuchi, kid, replay i dreyf.

MOSTY:
- (Yavnyy) Proveryaem podpis s `kid` i bez, okno dreyfa i blokirovku povtora po nonce (X-Request-Id).
- (Skrytyy #1) Multi-klyuch: P2P_HMAC_KEYS s main/prev.
- (Skrytyy #2) Sovmestimost verify_headers() interfeysa.

ZEMNOY ABZATs:
Garantiruet, chto dazhe pri rotatsii klyuchey i povtornykh popytkakh zloumyshlennika zaschita derzhitsya.

# c=a+b
"""
from __future__ import annotations
import os, time, hmac, hashlib
import pytest

from security.signing import verify_headers, sign
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _mk_sig(method, path, ts, body, key):
    can = f"{method}|{path}|{ts}|{hashlib.sha256(body).hexdigest()}"
    return hmac.new(key.encode(), can.encode(), hashlib.sha256).hexdigest()

@pytest.fixture(autouse=True)
def envkeys(monkeypatch):
    monkeypatch.setenv("P2P_SIGNING_REQUIRED","1")
    monkeypatch.setenv("P2P_DRIFT_SEC","120")
    monkeypatch.setenv("P2P_REPLAY_TTL_SEC","60")
    monkeypatch.setenv("P2P_HMAC_KEYS","main:KEYMAIN,prev:KEYPREV")
    yield

def test_verify_with_kid_and_rotation(monkeypatch):
    body=b'{"x":1}'
    ts=str(int(time.time()))
    sig=_mk_sig("POST","/api/v2/synergy/assign",ts,body,"KEYMAIN")
    ok,prob=verify_headers("POST","/api/v2/synergy/assign",body,{"X-P2P-Timestamp":ts,"X-P2P-Signature":sig,"X-P2P-Key-Id":"main"})
    assert ok and prob is None

    # tot zhe zapros starym klyuchom (prev)
    sig2=_mk_sig("POST","/api/v2/synergy/assign",ts,body,"KEYPREV")
    ok2,prob2=verify_headers("POST","/api/v2/synergy/assign",body,{"X-P2P-Timestamp":ts,"X-P2P-Signature":sig2,"X-P2P-Key-Id":"prev"})
    assert ok2 and prob2 is None

def test_replay_blocked_with_request_id(monkeypatch):
    body=b'{}'; ts=str(int(time.time()))
    sig=_mk_sig("GET","/api/v2/health",ts,body,"KEYMAIN")
    hdr={"X-P2P-Timestamp":ts,"X-P2P-Signature":sig,"X-P2P-Key-Id":"main","X-Request-Id":"RID-42"}
    ok1,prob1=verify_headers("GET","/api/v2/health",body,hdr)
    ok2,prob2=verify_headers("GET","/api/v2/health",body,hdr)
    assert ok1 and prob1 is None
    assert not ok2 and prob2 and prob2["title"]=="replay"

def test_timestamp_drift(monkeypatch):
    body=b'{}'
    ts=str(int(time.time())-99999)
    sig=_mk_sig("GET","/api/v2/health",ts,body,"KEYMAIN")
    ok,prob=verify_headers("GET","/api/v2/health",body,{"X-P2P-Timestamp":ts,"X-P2P-Signature":sig,"X-P2P-Key-Id":"main"})
    assert not ok and prob and "drift" in prob["title"]