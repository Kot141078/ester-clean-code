#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/mint_admin_jwt.py - offflayn-generator JWT (HS256) dlya "Ester".

Use:
  export JWT_SECRET="devsecret"
  python scripts/mint_admin_jwt.py --user owner --roles admin user --hours 12

Vyvodit gotovyy token v stdout.

Polya:
  - sub: <user>
  - roles: ["admin", ...]
  - iat/exp: unix-tag"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from typing import List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

def hs256(secret: bytes, signing_input: bytes) -> str:
    sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return b64url(sig)

def mint(user: str, roles: List[str], hours: int) -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        print("ERROR: set JWT_SECRET env", file=sys.stderr)
        sys.exit(2)

    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": user, "roles": roles, "iat": now, "exp": now + hours * 3600}

    h = b64url(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    p = b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("utf-8")
    s = hs256(secret.encode("utf-8"), signing_input)
    return f"{h}.{p}.{s}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="admin", help="znachenie sub")
    ap.add_argument("--roles", nargs="+", default=["admin"], help="spisok roley")
    ap.add_argument("--hours", type=int, default=24, help="token lifetime, hours")
    args = ap.parse_args()
    print(mint(args.user, args.roles, args.hours))

if __name__ == "__main__":
    main()