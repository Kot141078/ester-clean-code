# -*- coding: utf-8 -*-
"""scripts/jwt_keys_gen.py - generatsiya pary klyuchey dlya RS256 i sekreta dlya HS256.
Vyvodit faly:
  - jwt_rs256_private.pem
  - jwt_rs256_public.pem
  - jwt_hs256.secret
Ne menyaet kanon - simply utilita."""
from __future__ import annotations

import os
import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def gen_rs256(priv_path: str, pub_path: str):
    try:
        from cryptography.hazmat.backends import default_backend  # type: ignore
        from cryptography.hazmat.primitives import serialization  # type: ignore
        from cryptography.hazmat.primitives.asymmetric import rsa  # type: ignore
    except Exception as e:
        print("cryptography not installed. pip install cryptography", file=sys.stderr)
        raise e
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with open(priv_path, "wb") as f:
        f.write(priv)
    with open(pub_path, "wb") as f:
        f.write(pub)


def gen_hs256(path: str):
    import secrets

    key = secrets.token_urlsafe(64).encode("utf-8")
    with open(path, "wb") as f:
        f.write(key)


def main():
    out = os.getcwd()
    priv = os.path.join(out, "jwt_rs256_private.pem")
    pub = os.path.join(out, "jwt_rs256_public.pem")
    hs = os.path.join(out, "jwt_hs256.secret")
    gen_rs256(priv, pub)
    gen_hs256(hs)
    print("written:", priv, pub, hs)


if __name__ == "__main__":
    main()