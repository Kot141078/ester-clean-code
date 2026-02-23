#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generator klyuchey dlya Ester:
- Ed25519 (raw 32 bayta privatnyy, raw 32 bayta publichnyy) -> secrets/ed25519.sk, secrets/ed25519.pk
- AES Master Key (base64url 32 bayta) -> pechat v stdout i .env podskazka
"""
import base64
import os
import pathlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # type: ignore
from cryptography.hazmat.primitives.serialization import (  # type: ignore
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

root = pathlib.Path(".")
secrets_dir = root / "secrets"
secrets_dir.mkdir(exist_ok=True, parents=True)

# Ed25519
sk = Ed25519PrivateKey.generate()
sk_raw = sk.private_bytes(
    encoding=Encoding.Raw, format=PrivateFormat.Raw, encryption_algorithm=NoEncryption()
)
pk_raw = sk.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
(secrets_dir / "ed25519.sk").write_bytes(sk_raw)
(secrets_dir / "ed25519.pk").write_bytes(pk_raw)
print(f'Wrote {secrets_dir / "ed25519.sk"} and {secrets_dir / "ed25519.pk"}')

# AES master key
mk = os.urandom(32)
mk_b64 = base64.urlsafe_b64encode(mk).decode()
print("\nAdd this to your .env:")
print("ENCRYPTION_MASTER_KEY_BASE64=" + mk_b64)
