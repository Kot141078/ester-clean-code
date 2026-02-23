# -*- coding: utf-8 -*-
"""
tools/p2p/hmac_assign.py — CLI: sformirovat HMAC-podpis i (po zhelaniyu) otpravit zapros.

MOSTY:
- (Yavnyy) Pechataet canonical, ts, hex podpis, curl/PowerShell komandy.
- (Skrytyy #1) --send popytaetsya vypolnit zapros cherez requests (esli ustanovlen).
- (Skrytyy #2) Format podpisi sovmestim s /p2p/sign_example.

ZEMNOY ABZATs:
Odin vyzov — i u tebya gotovaya komanda, chtoby stuknut v assign s pravilnymi zagolovkami.

# c=a+b
"""
from __future__ import annotations
import os, sys, json, time, hmac, hashlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _sha256_hex(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def _hmac_hex(k: str, m: str) -> str: return hmac.new(k.encode(), m.encode(), hashlib.sha256).hexdigest()

def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.getenv("P2P_ASSIGN_URL","http://127.0.0.1:8080/api/v2/synergy/assign"))
    ap.add_argument("--team", default="Recon A")
    ap.add_argument("--operator", default="human.pilot")
    ap.add_argument("--ts", default=str(int(time.time())))
    ap.add_argument("--key", default=os.getenv("P2P_HMAC_KEY","devkey"))
    ap.add_argument("--send", action="store_true", help="Poprobovat otpravit zapros (esli est requests)")
    args = ap.parse_args(argv)

    body = {"team_id": args.team, "overrides": {"operator": args.operator}}
    body_str = json.dumps(body, ensure_ascii=False)
    sha = _sha256_hex(body_str.encode("utf-8"))
    canonical = f"POST|/api/v2/synergy/assign|{args.ts}|{sha}"
    sig = _hmac_hex(args.key, canonical)

    curl = f"curl -s -X POST \"{args.url}\" -H \"Content-Type: application/json\" -H \"X-Timestamp: {args.ts}\" -H \"X-Signature: {sig}\" --data '{body_str}'"
    ps = (
        "$ts = " + args.ts + "\n"
        "$sig = \"" + sig + "\"\n"
        "$body = '" + body_str.replace('\"','\"\"') + "'\n"
        f"Invoke-RestMethod -Uri '{args.url}' -Method Post -Headers @{{'Content-Type'='application/json';'X-Timestamp'=$ts;'X-Signature'=$sig}} -Body $body"
    )

    print("[p2p] canonical:", canonical)
    print("[p2p] signature:", sig)
    print("[p2p] curl:\n", curl)
    print("[p2p] powershell:\n", ps)

    if args.send:
        try:
            import requests  # type: ignore
            r = requests.post(args.url, headers={"Content-Type":"application/json","X-Timestamp":args.ts,"X-Signature":sig}, data=body_str, timeout=10)
            print("[p2p] HTTP", r.status_code, r.text[:2000])
        except Exception as e:
            print("[p2p] send failed:", e)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b