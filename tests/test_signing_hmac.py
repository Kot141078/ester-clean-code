# -*- coding: utf-8 -*-
import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _get_funcs(mod):
    # Sovmestimost s neskolkimi variantami imen v kanone
    candidates = [
        ("sign", "verify"),
        ("sign_bytes", "verify_bytes"),
        ("hmac_sign", "hmac_verify"),
    ]
    for s, v in candidates:
        if hasattr(mod, s) and hasattr(mod, v):
            return getattr(mod, s), getattr(mod, v)
    return None, None


def test_hmac_sign_verify():
    try:
        import security.signing as s  # type: ignore
    except Exception:
        pytest.skip("security.signing module not available")
    sign, verify = _get_funcs(s)
    if not sign or not verify:
        pytest.skip("No compatible sign/verify functions found")
    key = b"super-secret"
    data = b"payload"
    sig = sign(data, key)  # dopuskaem signatury (data,key) ili (key,data)
    # Esli biblioteka ispolzuet (key,data), poprobuem inversiyu
    ok = verify(data, key, sig) if sig is not None else False
    if not ok:
        # Poprobuem druguyu rasstanovku argumentov
        sig2 = sign(key, data)
        ok = verify(key, data, sig2)
    assert ok is True
    # Negativnaya proverka
    bad = verify(b"other", key, sig) or verify(data, b"other", sig)
    assert bad is False
