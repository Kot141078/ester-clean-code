#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S0/tools/jwt_mint.py — lokalnaya vydacha HS256-JWT bez vneshnikh zavisimostey (bibliotek).

Mosty:
- Yavnyy: Dzheynes (bayes) → claims tokena — eto "apriory" dostupa; verifikator obnovlyaet veru o subekte.
- Skrytyy #1: Enderton (logika) → rol = predikat; proverka roley — kompozitsiya bulevykh formul nad claims.
- Skrytyy #2: Ashby (kibernetika) → TTL/refresh ogranichivayut "raznoobrazie" povedeniya, uderzhivaya sistemu v norme.

Zemnoy abzats (inzheneriya):
Skript delaet JWT vruchnuyu: base64url(header).base64url(payload).HMAC_SHA256(secret).
Nuzhen tolko `JWT_SECRET`. Po umolchaniyu = "devsecret" (dlya stenda), na prod stav 64-simvolnyy.
Sovmestim s bolshinstvom Flask-proverok HS256. Ne menyaet prilozhenie.

# c=a+b
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import hmac
import json
import os
import time
from typing import List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def sign_hs256(secret: str, header: dict, payload: dict) -> str:
    header_b64 = b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    msg = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{b64url(sig)}"

def main():
    ap = argparse.ArgumentParser(description="Mint HS256 JWT (offline, no deps)")
    ap.add_argument("--user", required=True, help="Imya/login subekta (sub)")
    ap.add_argument("--role", default="user", help="Role: guest/user/admin")
    ap.add_argument("--ttl", type=int, default=3600, help="Vremya zhizni tokena (sek)")
    ap.add_argument("--aud", default="ester-ui", help="aud claim")
    ap.add_argument("--iss", default="ester-local", help="iss claim")
    ap.add_argument("--alg", default="HS256", help="alg (HS256)")
    ap.add_argument("--kid", default="local-dev", help="kid dlya rotatsii sekretov")
    args = ap.parse_args()

    now = int(time.time())
    payload = {
        "iss": args.iss,
        "aud": args.aud,
        "iat": now,
        "nbf": now,
        "exp": now + int(args.ttl),
        "sub": args.user,
        "roles": [args.role],
        "name": args.user,
    }
    header = {"typ": "JWT", "alg": args.alg, "kid": args.kid}
    secret = os.environ.get("JWT_SECRET", "devsecret")
    token = sign_hs256(secret, header, payload)
    print(token)

if __name__ == "__main__":
    raise SystemExit(main())
