#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vypusk dev-JWT s rolyami.
Ispolzuet HS256, esli zadan JWT_SECRET/JWT_SECRET_KEY.
Inache pytaetsya RS256 iz JWT_PRIVATE_KEY_PATH.
"""
import json
import os
import sys
import time

import jwt  # PyJWT
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

roles = sys.argv[1:] or ["admin"]
claims = {
    "sub": "dev-user",
    "roles": roles,
    "iat": int(time.time()),
    "exp": int(time.time()) + 3600,
}

alg = (os.getenv("JWT_ALGORITHM") or "").upper()
if (os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET_KEY")) and alg in (
    "",
    "HS256",
    None,
):
    key = os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET_KEY")
    tok = jwt.encode(claims, key, algorithm="HS256")
    print(tok)
    sys.exit(0)

priv_path = os.getenv("JWT_PRIVATE_KEY_PATH", "").strip()
if priv_path and os.path.exists(priv_path):
    key = open(priv_path, "r", encoding="utf-8").read()
    alg = "RS256" if alg == "" else alg
    tok = jwt.encode(claims, key, algorithm=alg)
    print(tok)
    sys.exit(0)

print(
    "No suitable JWT config found. Set JWT_SECRET or provide JWT_PRIVATE_KEY_PATH.",
    file=sys.stderr,
)
sys.exit(2)