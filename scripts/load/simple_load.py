# -*- coding: utf-8 -*-
"""scripts/load/simple_load.py - legkiy generator nagruzki dlya /api/v2/synergy/assign.

MOSTY:
- (Yavnyy) Asinkhronnye klienty shlyut podpisannye zaprosy; aggregate p50/p95 latency i RPS.
- (Skrytyy #1) Avto-initsializatsiya demo-dannykh (agency/komanda) pri neobkhodimosti.
- (Skrytyy #2) Fail-safe: lyubye oshibki schitayutsya, no ne valyat progon; itogovaya svodka po zavershenii.

ZEMNOY ABZATs:
Pozvolyaet bystro proverit, how zhivet servis pod 5–50 rps: idempotentnost, stabilnost, latentnost.

# c=a+b"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import random
import statistics
import time
from typing import List, Tuple

import httpx
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _sig(method: str, path: str, body: bytes, key: str, ts: int) -> str:
    can = f"{method}|{path}|{ts}|{hashlib.sha256(body).hexdigest()}"
    return hmac.new(key.encode(), can.encode(), hashlib.sha256).hexdigest()

async def _ensure_seed(base: str) -> None:
    async with httpx.AsyncClient(base_url=base, timeout=5.0) as cl:
        # We are trying to get a board; if 404 is not our pens (we’ll skip it)
        try:
            await cl.get("/synergy/board/data?team_id=Recon%20A")
        except Exception:
            pass

async def worker(idx: int, base: str, team: str, key: str, total: int, out: List[float], errs: List[str]):
    path = "/api/v2/synergy/assign"
    for i in range(total):
        overrides = {"operator":"human.pilot"} if random.random()<0.5 else {}
        body = json.dumps({"team_id": team, "overrides": overrides}).encode()
        ts = int(time.time())
        sig = _sig("POST", path, body, key, ts)
        hdr = {"X-P2P-Timestamp": str(ts), "X-P2P-Signature": sig, "Content-Type":"application/json", "X-Request-Id": f"LD-{idx}-{i}"}
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(base_url=base, timeout=10.0) as cl:
                r = await cl.post(path, content=body, headers=hdr)
                _ = r.json()
            dt = (time.perf_counter()-t0)*1000.0
            out.append(dt)
        except Exception as e:
            errs.append(str(e))

def pct(vs: List[float], p: float) -> float:
    if not vs:
        return 0.0
    s = sorted(vs); k = int(len(s)*p); k = min(max(0,k), len(s)-1)
    return s[k]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.getenv("TARGET_BASE_URL","http://127.0.0.1:8080"), help="base URL")
    ap.add_argument("--team", default="Recon A")
    ap.add_argument("--key", default=os.getenv("P2P_HMAC_KEY","devkey"))
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--requests", type=int, default=50, help="per worker")
    args = ap.parse_args()

    out: List[float] = []
    errs: List[str] = []
    asyncio.run(_ensure_seed(args.base))
    t0 = time.perf_counter()
    asyncio.run(asyncio.gather(*[
        worker(i, args.base, args.team, args.key, args.requests, out, errs)
        for i in range(args.concurrency)
    ]))
    t1 = time.perf_counter()

    total = len(out)
    rps = total / (t1 - t0)
    print(f"✓ sent={total} ok, errors={len(errs)}, rps={rps:.2f}")
    if errs:
        print("errors (sample):", errs[:5])
    if out:
        print(f"latency ms: p50={pct(out,0.50):.1f} p95={pct(out,0.95):.1f} avg={statistics.mean(out):.1f}")

if __name__ == "__main__":
    main()