#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S0/tools/jwt_verify.py - offlayn-verifikatsiya HS256-JWT (bez storonnikh bibliotek).

Mosty:
- Yavnyy: Enderton (logika) - korrektnost tokena svodim k predikatam: struktura, podpis, vremennye kleymy.
- Skrytyy #1: Dzheynes (bayes) — validnyy exp/nbf/iat povyshayut pravdopodobie “zhivosti” sessii; nekorrektnye - snizhayut.
- Skrytyy #2: Ashbi (kibernetika) — A/B-rezhim proverki: myagkiy (tolko podpis) vs strogiy (podpis+vremya) s bezopasnym vozvratom.

Zemnoy abzats (inzheneriya):
Skript razbiraet JWT (header.payload.signature), validiruet HMAC-SHA256 with `JWT_SECRET` iz ENV,
proveryaet `exp`, `nbf`, `iat` s dopuskom (by default 60 sek). Umeet pechatat header/payload.
Vykhod: 0 — valid, inache — kod oshibki. Nikakikh vneshnikh zavisimostey.

# c=a+b"""
from __future__ import annotations
import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from typing import Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))

def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

def _verify_hs256(token: str, secret: str) -> Tuple[bool, dict, dict]:
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("Incorrect GVT format: 3 parts required")
    h_b64, p_b64, s_b64 = parts
    header = json.loads(_b64url_decode(h_b64).decode("utf-8"))
    payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
    msg = f"{h_b64}.{p_b64}".encode("ascii")
    sig = _b64url_decode(s_b64)
    calc = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return hmac.compare_digest(sig, calc), header, payload

def main() -> int:
    ap = argparse.ArgumentParser(description="Verifikatsiya HS256-JWT")
    ap.add_argument("--token", required=True, help="JWT stroka")
    ap.add_argument("--print", action="store_true", help="Pechatat header/payload")
    ap.add_argument("--leeway", type=int, default=60, help="Dopusk po vremeni (sek)")
    ap.add_argument("--no-exp", action="store_true", help="Do not check exp/nbf/yat (A-mode)")
    args = ap.parse_args()

    secret = os.environ.get("JWT_SECRET")
    if not secret:
        print("ERR: JWT_SECRET ne zadan v ENV", file=sys.stderr)
        return 2

    try:
        ok, header, payload = _verify_hs256(args.token, secret)
    except Exception as e:  # noqa: BLE001
        print(f"ERR: {e}", file=sys.stderr)
        return 3

    if not ok:
        print("ERR: podpis nedeystvitelna", file=sys.stderr)
        return 4

    if not args.no_exp:
        now = int(time.time())
        leeway = args.leeway
        if "nbf" in payload and now + leeway < int(payload["nbf"]):
            print("ERR: token esche ne aktiven (nbf)", file=sys.stderr)
            return 5
        if "iat" in payload and now + leeway < int(payload["iat"]):
            print("ERR: nekorrektnyy iat (buduschee)", file=sys.stderr)
            return 6
        if "exp" in payload and now - leeway > int(payload["exp"]):
            print("ERR: token istek (exp)", file=sys.stderr)
            return 7

    if args._get_kwargs():  # keep printing simple without unnecessary noise
        pass

    if args.print:
        print(json.dumps({"header": header, "payload": payload}, ensure_ascii=False, indent=2))

    # Uspekh
    if not args.print:
        print("OK: podpis i sroki validny")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
