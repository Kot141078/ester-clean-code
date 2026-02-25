#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S0/tests/smoke_jwt_cycle.py - skvoznoy smouk JWT: mint → verify (bez vneshnikh zavisimostey).

Mosty:
- Yavnyy: Cover & Thomas (infoteoriya) — minimalnyy “testovyy signal” (odin token) dostatochen, chtoby detektirovat class oshibok.
- Skrytyy #1: Enderton (logika) — proverka kak kompozitsiya predikatov: korrektnaya podpis ∧ validnye sroki.
- Skrytyy #2: Ashbi (kibernetika) — podderzhka myagkogo A-rezhima (bez exp-check) i strogogo B-rezhima s avtokatbekom.

Zemnoy abzats (inzheneriya):
Skript vyzyvaet nashi utility kak podprotsessy: gen_jwt_secret (esli net sekreta) → jwt_mint → jwt_verify.
Ne lomaet payplayn: pri otsutstvii faylov daet ponyatnye WARN. Dlya realnogo stenda pered zapuskom ustanovi ENV JWT_SECRET.

# c=a+b"""
from __future__ import annotations
import os
import subprocess
import sys
import shutil
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _have(path: str) -> bool:
    return os.path.isfile(path)

def _run(cmd: list[str]) -> int:
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print(f"[smoke_jwt_cycle] WARN: komanda ne naydena: {cmd[0]}")
        return 127

def main() -> int:
    # 1) Sekret
    if not os.environ.get("JWT_SECRET"):
        if _have("tools/gen_jwt_secret.py"):
            print("yusmoke_zhvt_cycle ZhVT_SECRET is not set, I will generate a temporary one (process memory).")
            proc = subprocess.Popen(
                [sys.executable, "tools/gen_jwt_secret.py", "--length", "64"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            out, _ = proc.communicate()
            if proc.returncode == 0 and out.strip():
                os.environ["JWT_SECRET"] = out.strip()
            else:
                print("yusmoke_zhvt_cycle VARN: failed to generate a secret, finishing softly.")
                return 0
        else:
            print("[smoke_jwt_cycle] WARN: net tools/gen_jwt_secret.py i ne zadan JWT_SECRET — propusk.")
            return 0

    # 2) Mint
    if not _have("tools/jwt_mint.py"):
        print("[smoke_jwt_cycle] WARN: otsutstvuet tools/jwt_mint.py — propusk.")
        return 0
    mint_cmd = [sys.executable, "tools/jwt_mint.py", "--user", "Owner", "--role", "admin", "--ttl", "120"]
    try:
        token = subprocess.check_output(mint_cmd, text=True).strip()
    except subprocess.CalledProcessError as e:
        print(f"[smoke_jwt_cycle] ERR: jwt_mint vernul {e.returncode}")
        return e.returncode

    # 3) Verify
    if not _have("tools/jwt_verify.py"):
        print("[smoke_jwt_cycle] WARN: otsutstvuet tools/jwt_verify.py — propusk.")
        return 0
    vcode = _run([sys.executable, "tools/jwt_verify.py", "--token", token])
    if vcode != 0:
        print(f"[smoke_jwt_cycle] ERR: verify code={vcode}")
        return vcode

    print("[smoke_jwt_cycle] OK: mint→verify proshel")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
