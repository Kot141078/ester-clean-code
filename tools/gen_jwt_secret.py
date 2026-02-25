#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S0/tools/gen_jwt_secret.py - generator stoykogo sekreta dlya HS256-JWT (offlayn, bez zavisimostey).

Mosty:
- Yavnyy: Dzheynes (bayes) — silnyy sekret povyshaet apriornuyu “nepravdopodobnost” poddelki tokena; ataka stanovitsya informatsionno nevygodnoy.
- Skrytyy #1: Enderton (logika) — validatsiya parametrov kak proveryaemye predikaty nad dlinoy/alfavitom; determinirovannye vyvody.
- Skrytyy #2: Ashbi (kibernetika) - A/B-slot upravleniya: bezopasnyy A (tolko pechat), i B (zapis v .env) s avtokatbekom.

Zemnoy abzats (inzheneriya):
Skript ispolzuet kriptograficheskiy generator `secrets.token_bytes` i kodiruet v base64url or hex.
Po umolchaniyu vydaet 64-simvolnuyu base64url-stroku (bez '='). Rezhimy:
  --mode base64url|hex|alnum (by default base64url)
  --length <N> (recommenduetsya >= 64)
  --write-dotenv .env (AB_MODE=B) — bezopasno dopishet/upnovit JWT_SECRET; pri oshibke - avtokatbek (tolko pechat).
Nikakikh vneshnikh bibliotek. Sovmestim s nashim HS256.

# c=a+b"""
from __future__ import annotations
import argparse
import base64
import os
import re
import secrets
import string
import sys
from typing import Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _gen_base64url(nchars: int) -> str:
    # Generates enough bytes so that after basier64irl without b=b it turns out >= nchars, then cut it off.
    # 3 bayta ~ 4 simvola base64 -> otsenim zapasom *2.
    buf = secrets.token_bytes(max(8, (nchars * 2)))
    s = base64.urlsafe_b64encode(buf).decode("ascii").rstrip("=")
    if len(s) < nchars:
        # If it’s suddenly short, we’ll get more
        needed = nchars - len(s)
        s += base64.urlsafe_b64encode(secrets.token_bytes(max(8, needed))).decode("ascii").rstrip("=")
    return s[:nchars]

def _gen_hex(nchars: int) -> str:
    # hex daet 2 simvola na bayt → nuzhno nchars//2 bayt
    nbytes = max(16, (nchars + 1) // 2)
    s = secrets.token_hex(nbytes)
    return s[:nchars]

def _gen_alnum(nchars: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(nchars))

def _write_dotenv(path: str, key: str, val: str) -> Tuple[bool, str]:
    try:
        content = ""
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        # If the key is already there, replace it; otherwise - add to the end.
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
        if pattern.search(content):
            content = pattern.sub(f"{key}={val}", content)
        else:
            if content and not content.endswith("\n"):
                content += "\n"
            content += f"{key}={val}\n"
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
        return True, f"Recorded in ZZF0Z (key ZZF1ZZ)."
    except Exception as e:  # noqa: BLE001
        return False, f"Failed to write to ZZF0Z: ZZF1ZZ"

def main() -> int:
    ap = argparse.ArgumentParser(description="Generator sekreta JWT (HS256)")
    ap.add_argument("--length", type=int, default=64, help="Dlina sekreta (rekomenduetsya ≥64)")
    ap.add_argument("--mode", choices=["base64url", "hex", "alnum"], default="base64url", help="Alfavit")
    ap.add_argument("--write-dotenv", dest="dotenv", default="", help="Path to .env for the ZhVT_SEKRET entry")
    args = ap.parse_args()

    L = max(32, args.length)  # nizhniy porog bezopasnosti
    if args.mode == "base64url":
        secret = _gen_base64url(L)
    elif args.mode == "hex":
        secret = _gen_hex(L)
    else:
        secret = _gen_alnum(L)

    print(secret)

    # A/B slot: default A (print). If --lie-dotenv is explicitly specified, we consider mode B.
    if args.dotenv:
        ok, msg = _write_dotenv(args.dotenv, "JWT_SECRET", secret)
        if ok:
            print(f"[gen_jwt_secret] OK: {msg}", file=sys.stderr)
        else:
            print(f"yugen_zhvt_secretsch VARN: ZZF0Z — auto-cutback to A-mode (print only).", file=sys.stderr)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
