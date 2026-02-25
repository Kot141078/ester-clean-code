# security/jwt_glue.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, time, typing as t
import jwt
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = [
    "select_ab_slot", "get_secret", "get_algorithm",
    "mint", "decode", "status",
]

def select_ab_slot() -> str:
    """A/B slot from the environment; by default bAb."""
    ab = os.environ.get("ESTER_JWT_BOOTSTRAP_AB", "A").strip().upper()
    return "A" if ab not in ("A","B") else ab

def get_secret() -> str:
    """Edinaya tochka: esli A → JWT_SECRET_KEY_A or fallback JWT_SECRET_KEY,
                 esli B → JWT_SECRET_KEY_B or fallback JWT_SECRET_KEY."""
    ab = select_ab_slot()
    base = os.environ.get("JWT_SECRET_KEY") or os.environ.get("ESTER_JWT_SECRET") or ""
    if ab == "A":
        secret = os.environ.get("JWT_SECRET_KEY_A") or base
    else:
        secret = os.environ.get("JWT_SECRET_KEY_B") or base
    if not secret:
        raise RuntimeError("JWT secret is required (set ESTER_JWT_SECRET or JWT_SECRET_KEY).")
    return secret

def get_algorithm() -> str:
    """Algoritm podpisi (po umolchaniyu HS256)."""
    return os.environ.get("JWT_ALGORITHM", "HS256")

def mint(
    sub: str,
    roles: t.Sequence[str] = ("USER",),
    hours: int = 12,
    extra: t.Optional[dict] = None,
) -> str:
    """Sign the token with the same secret/algorithm that the verifiers expect."""
    n = int(time.time())
    claims = {
        "sub": sub,
        "roles": list(roles),
        "iss": "ester",
        "aud": "ester",
        "iat": n,
        "exp": n + hours * 60 * 60,
    }
    if extra:
        claims.update(extra)
    tok = jwt.encode(claims, get_secret(), algorithm=get_algorithm())
    return tok if isinstance(tok, str) else tok.decode()

def decode(token: str) -> dict:
    """Check the signature and return the payload (if it is not valid, there is an exception)."""
    return jwt.decode(
        token,
        get_secret(),
        algorithms=[get_algorithm()],
        audience="ester",
        issuer="ester",
    )

def status() -> dict:
    """Telemetry without secret (for /outn/glue/status)."""
    return {
        "ab": select_ab_slot(),
        "alg": get_algorithm(),
        "token_location": ["headers", "query_string"],
        "header": {"name": "Authorization", "type": "Bearer"},
        "has_secret": bool(get_secret()),
    }
