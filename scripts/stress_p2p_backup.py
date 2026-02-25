# -*- coding: utf-8 -*-
"""scripts/stress_p2p_backup.py - stsenariy nagruzki replikatsii i bekapa Ester.

Zapusk (primer):
  python scripts/stress_p2p_backup.py --base http://localhost:5000\
    --concurrency 32 --duration 45 --secret "<set-via-env-or-arg>"

Parametry:
  --base bazovyy URL instansa Ester
  --replicate put replikatsii (po umolchaniyu /p2p/replicate)
  --backup put bekapa (po umolchaniyu /backup/run)
  --concurrency kolichestvo potokov
  --duration dlitelnost, sek
  --secret JWT_SECRET (HS256), chtoby sgenerirovat admin-token
  --jwt gotovyy JWT (esli zadan, secret ignoriruetsya)
  --profile-out put dlya profayla .prof (optsionalno)

Vyvodit JSON-metriki po kazhdomu URL."""
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Dict, List, Tuple

import jwt  # PyJWT

from profiling.simple_profiler import profile_block, run_http_burst
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def mint_admin_jwt(secret: str, ttl_sec: int = 3600) -> str:
    import datetime as dt

    now = int(time.time())
    payload = {
        "sub": "stress-runner",
        "role": "admin",
        "roles": ["admin"],
        "iat": now,
        "exp": now + ttl_sec,
    }
    return jwt.encode(payload, secret, algorithm="HS256")  # type: ignore


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base", type=str, default=os.getenv("ESTER_BASE_URL", "http://localhost:5000")
    )
    ap.add_argument("--replicate", type=str, default=os.getenv("ESTER_REPL_PATH", "/p2p/replicate"))
    ap.add_argument("--backup", type=str, default=os.getenv("ESTER_BACKUP_PATH", "/backup/run"))
    ap.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("ESTER_STRESS_CONCURRENCY", "16")),
    )
    ap.add_argument("--duration", type=int, default=int(os.getenv("ESTER_STRESS_DURATION", "30")))
    ap.add_argument("--secret", type=str, default=os.getenv("JWT_SECRET", ""))
    ap.add_argument("--jwt", type=str, default=os.getenv("ESTER_JWT", ""))
    ap.add_argument("--profile-out", type=str, default=os.getenv("ESTER_PROFILE_OUT", ""))
    args = ap.parse_args()

    if not args.jwt and not args.secret:
        raise RuntimeError("Set JWT_SECRET/ESTER_JWT_SECRET or pass --jwt/--secret explicitly.")
    token = args.jwt or mint_admin_jwt(args.secret)
    headers = {"Authorization": f"Bearer {token}"}
    urls: List[Tuple[str, str]] = [
        ("POST", args.base.rstrip("/") + args.replicate),
        ("POST", args.base.rstrip("/") + args.backup),
    ]

    if args.profile_out:
        with profile_block(args.profile_out):
            res = run_http_burst(
                urls,
                concurrency=args.concurrency,
                duration_sec=args.duration,
                headers=headers,
            )
    else:
        res = run_http_burst(
            urls,
            concurrency=args.concurrency,
            duration_sec=args.duration,
            headers=headers,
        )

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
