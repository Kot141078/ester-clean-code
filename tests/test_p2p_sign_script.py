# -*- coding: utf-8 -*-
import hashlib
import hmac
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def test_sign_formula_matches_reference():
    from scripts.p2p_sign import sign  # type: ignore

    secret = "s3cr3t"
    ts = 1700000000
    method = "POST"
    path = "/p2p/echo"
    body = b'{"x":1}'

    ref_msg = f"{ts}\n{method}\n{path}\n{_sha256_hex(body)}".encode("utf-8")
    ref_sig = hmac.new(secret.encode("utf-8"), ref_msg, hashlib.sha256).hexdigest()

    sig = sign(secret, ts, method, path, body)
    assert sig == ref_sig