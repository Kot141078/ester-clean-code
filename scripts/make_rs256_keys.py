#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generatsiya RSA-klyuchey dlya RS256 JWT (optsionalno).
Flask-JWT-Extended will be used:
  JWT_ALGORITHM=RS256
  JWT_PRIVATE_KEY=<soderzhimoe privatnogo klyucha PEM>
  JWT_PUBLIC_KEY=<soderzhimoe publichnogo klyucha PEM>

Skript sozdaet dva fayla v ukazannoy direktorii (po umolchaniyu ./secrets):
  - jwt_rs256_private.pem
  - jwt_rs256_public.pem"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except Exception as e:  # pragma: no cover
    print(
        "Trebuetsya paket 'cryptography' (pip install cryptography)", file=sys.stderr
    )
    raise


def main() -> int:
    out_dir = Path(os.getenv("SECRETS_DIR", "./secrets")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()

    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,  # PKCS#1
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    priv_path = out_dir / "jwt_rs256_private.pem"
    pub_path = out_dir / "jwt_rs256_public.pem"
    priv_path.write_bytes(priv_pem)
    pub_path.write_bytes(pub_pem)

    print(f"Private: {priv_path}")
    print(f"Public : {pub_path}")
    print("Export to the environment for Flask-ZhVT-Extended:")
    print("  export JWT_ALGORITHM=RS256")
    print('  export JWT_PRIVATE_KEY="$(cat secrets/jwt_rs256_private.pem)"')
    print('  export JWT_PUBLIC_KEY="$(cat secrets/jwt_rs256_public.pem)"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())