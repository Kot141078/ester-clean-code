# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECRETS_DIR = ROOT / "secrets"
PK_PATH = SECRETS_DIR / "ed25519.pk"
SK_PATH = SECRETS_DIR / "ed25519.sk"


def _allow_write() -> bool:
    raw = str(os.getenv("ESTER_ALLOW_SECRET_WRITE", "0")).strip().lower()
    return raw in {"1", "true", "yes", "on", "y"}


def _gen_keypair() -> tuple[bytes, bytes, str]:
    try:
        from nacl.signing import SigningKey  # type: ignore

        sk = SigningKey.generate()
        seed = bytes(sk)
        pk = bytes(sk.verify_key)
        return pk, seed + pk, "ed25519"
    except Exception:
        # Offline-safe fallback when PyNaCl is unavailable.
        pk = secrets.token_bytes(32)
        sk = secrets.token_bytes(64)
        return pk, sk, "fallback_random"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Overwrite existing keys.")
    args = ap.parse_args(argv)

    if not _allow_write():
        print("DENY: set ESTER_ALLOW_SECRET_WRITE=1 to initialize secrets.")
        return 2

    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    if (PK_PATH.exists() or SK_PATH.exists()) and not args.force:
        print("SKIP: secrets already exist (use --force to overwrite).")
        return 0

    pk, sk, alg = _gen_keypair()
    PK_PATH.write_bytes(pk)
    SK_PATH.write_bytes(sk)
    print(f"OK: initialized secrets (alg={alg})")
    print(f"pk={PK_PATH}")
    print(f"sk={SK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
